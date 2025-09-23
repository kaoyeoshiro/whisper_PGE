#!/usr/bin/env python3
"""
WhisperPGE Launcher - Simplified version
"""

import os
import sys
import subprocess
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from pathlib import Path
import warnings
import time
import tempfile

# Optional imports for enhanced functionality
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import requests
    import zipfile
    from packaging import version
    UPDATE_AVAILABLE = True
except ImportError:
    UPDATE_AVAILABLE = False

warnings.filterwarnings("ignore")

# Single instance control
INSTANCE_LOCK_FILE = Path(tempfile.gettempdir()) / "whisper_pge_running.lock"

def is_already_running():
    """Check if another instance is already running."""
    if not INSTANCE_LOCK_FILE.exists():
        return False

    try:
        with open(INSTANCE_LOCK_FILE, 'r') as f:
            pid = int(f.read().strip())

        # Check if process is still running
        if PSUTIL_AVAILABLE:
            if psutil.pid_exists(pid):
                try:
                    proc = psutil.Process(pid)
                    if 'WhisperPGE' in proc.name():
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        else:
            # Fallback method without psutil (less reliable)
            import signal
            try:
                os.kill(pid, 0)  # Signal 0 checks if process exists
                return True  # Process exists
            except (OSError, ProcessLookupError):
                pass  # Process doesn't exist

        # Remove stale lock file
        INSTANCE_LOCK_FILE.unlink()
        return False
    except:
        return False

def create_instance_lock():
    """Create instance lock file."""
    try:
        with open(INSTANCE_LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        return True
    except:
        return False

def remove_instance_lock():
    """Remove instance lock file."""
    try:
        if INSTANCE_LOCK_FILE.exists():
            INSTANCE_LOCK_FILE.unlink()
    except:
        pass

def get_app_version() -> str:
    """Resolve the app version from bundled metadata."""
    candidate_paths = []
    if hasattr(sys, "_MEIPASS"):
        candidate_paths.append(Path(sys._MEIPASS) / "app" / "version.json")
    candidate_paths.append(Path(__file__).resolve().parent / "app" / "version.json")

    for path in candidate_paths:
        try:
            if path.exists():
                with path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                    version = data.get("version")
                    if version:
                        return str(version)
        except Exception:
            continue
    return "dev"

APP_VERSION = get_app_version()
GITHUB_REPO = "kaoyeoshiro/whisper_PGE"
UPDATE_CHECK_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

def check_for_updates():
    """Check for newer versions on GitHub"""
    if not UPDATE_AVAILABLE:
        print("Bibliotecas de atualização não disponíveis")
        return {"available": False}

    try:
        print(f"Verificando atualizações... Versão atual: {APP_VERSION}")
        response = requests.get(UPDATE_CHECK_URL, timeout=10)
        if response.status_code == 200:
            release_data = response.json()
            latest_version = release_data["tag_name"].lstrip("v")

            if version.parse(latest_version) > version.parse(APP_VERSION):
                print(f"Nova versão disponível: {latest_version}")
                return {
                    "available": True,
                    "version": latest_version,
                    "download_url": None,
                    "release_data": release_data
                }

        print("Aplicação está atualizada")
        return {"available": False}
    except Exception as e:
        print(f"Erro ao verificar atualizações: {e}")
        return {"available": False}

def download_and_install_update(release_data):
    """Download and install update"""
    try:
        # Find the installer asset
        assets = release_data.get("assets", [])
        installer_asset = None

        for asset in assets:
            if asset["name"].endswith(".exe") and "Installer" in asset["name"]:
                installer_asset = asset
                break

        if not installer_asset:
            raise Exception("Arquivo de instalação não encontrado no release")

        # Download the new installer
        download_url = installer_asset["browser_download_url"]
        temp_dir = Path(tempfile.gettempdir())
        temp_installer = temp_dir / f"WhisperPGE_Update_{release_data['tag_name']}.exe"

        print(f"Baixando atualização de {download_url}")
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(temp_installer, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"Download: {progress:.1f}%", end='\r')

        print(f"\nDownload concluído: {temp_installer}")

        # Run the new installer
        print("Iniciando instalação da atualização...")
        subprocess.Popen([str(temp_installer)], shell=True)

        # Exit current instance
        return True

    except Exception as e:
        print(f"Erro durante atualização: {e}")
        return False

def show_update_dialog(update_info):
    """Show update available dialog"""
    root = tk.Tk()
    root.title(f"WhisperPGE v{APP_VERSION} - Atualização Disponível")
    root.geometry("500x300")
    root.resizable(False, False)

    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (500 // 2)
    y = (root.winfo_screenheight() // 2) - (300 // 2)
    root.geometry(f"500x300+{x}+{y}")

    frame = ttk.Frame(root, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    # Title
    ttk.Label(frame, text="Nova versão disponível!",
              font=("Arial", 16, "bold")).pack(pady=(0, 10))

    # Version info
    ttk.Label(frame, text=f"Versão atual: {APP_VERSION}",
              font=("Arial", 10)).pack(pady=2)
    ttk.Label(frame, text=f"Nova versão: {update_info['version']}",
              font=("Arial", 10, "bold")).pack(pady=2)

    # Release notes if available
    release_notes = update_info.get('release_data', {}).get('body', '')
    if release_notes:
        ttk.Label(frame, text="Novidades:", font=("Arial", 10, "bold")).pack(pady=(10, 5))

        text_frame = ttk.Frame(frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        text_widget = tk.Text(text_frame, height=6, wrap=tk.WORD, font=("Arial", 9))
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget.insert('1.0', release_notes[:500] + ('...' if len(release_notes) > 500 else ''))
        text_widget.config(state=tk.DISABLED)

    # Buttons
    button_frame = ttk.Frame(frame)
    button_frame.pack(pady=10)

    user_choice = [None]

    def update_now():
        user_choice[0] = True
        root.destroy()

    def skip_update():
        user_choice[0] = False
        root.destroy()

    ttk.Button(button_frame, text="Atualizar Agora",
               command=update_now).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Pular",
               command=skip_update).pack(side=tk.LEFT, padx=5)

    # Make update button default
    root.bind('<Return>', lambda e: update_now())

    root.mainloop()
    return user_choice[0]

def check_dependencies_simple():
    """Simple dependency check"""
    try:
        torch_test = subprocess.run([
            sys.executable, "-c", "import torch"
        ], capture_output=True, text=True, timeout=10)

        whisper_test = subprocess.run([
            sys.executable, "-c", "import whisper"
        ], capture_output=True, text=True, timeout=10)

        return torch_test.returncode == 0 and whisper_test.returncode == 0
    except:
        return False

def install_dependencies():
    """Show simple installation dialog"""
    root = tk.Tk()
    root.title(f"WhisperPGE v{APP_VERSION} - Instalação")
    root.geometry("500x300")

    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (500 // 2)
    y = (root.winfo_screenheight() // 2) - (300 // 2)
    root.geometry(f"500x300+{x}+{y}")

    frame = ttk.Frame(root, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="WhisperPGE - Instalação de Dependências",
              font=("Arial", 14, "bold")).pack(pady=(0, 10))

    ttk.Label(frame, text="Instalando PyTorch e Whisper...\nPor favor, aguarde.",
              font=("Arial", 10)).pack(pady=(0, 20))

    progress = ttk.Progressbar(frame, mode='indeterminate')
    progress.pack(fill=tk.X, pady=(0, 10))
    progress.start()

    status_label = ttk.Label(frame, text="Preparando...", font=("Arial", 9))
    status_label.pack(pady=(0, 10))

    install_success = [False]

    def install_worker():
        try:
            status_label.config(text="Instalando PyTorch...")
            root.update()

            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "--no-cache-dir",
                "torch==2.0.1+cpu", "torchaudio==2.0.2+cpu",
                "--index-url", "https://download.pytorch.org/whl/cpu"
            ], capture_output=True, text=True)

            if result.returncode != 0:
                # Fallback to standard torch
                result = subprocess.run([
                    sys.executable, "-m", "pip", "install", "--no-cache-dir",
                    "torch", "torchaudio"
                ], capture_output=True, text=True)

            status_label.config(text="Instalando Whisper...")
            root.update()

            result2 = subprocess.run([
                sys.executable, "-m", "pip", "install", "--no-cache-dir",
                "openai-whisper", "numpy", "requests"
            ], capture_output=True, text=True)

            if result.returncode == 0 and result2.returncode == 0:
                install_success[0] = True
                status_label.config(text="Instalação concluída!")
                progress.stop()
                progress.config(mode='determinate', value=100)

                ttk.Button(frame, text="Continuar",
                          command=root.destroy).pack(pady=10)
            else:
                status_label.config(text="Erro na instalação")
                ttk.Button(frame, text="Fechar",
                          command=root.destroy).pack(pady=10)

        except Exception as e:
            status_label.config(text=f"Erro: {str(e)}")
            ttk.Button(frame, text="Fechar",
                      command=root.destroy).pack(pady=10)

    thread = threading.Thread(target=install_worker, daemon=True)
    thread.start()

    root.mainloop()
    return install_success[0]

# === WHISPER APPLICATION CODE ===

class TranscricaoCancelada(Exception):
    """Exceção usada para sinalizar cancelamento da transcrição"""
    pass

class WhisperTranscriber:
    """Aplicação de transcrição local usando Whisper"""

    def __init__(self, root):
        self.root = root
        self.root.title(f"Whisper PGE v{APP_VERSION}")
        self.root.geometry("800x400")

        # Variáveis de controle
        self.arquivos_selecionados = []
        self.pasta_saida = None
        self.modelo_carregado = None
        self.modelo_atual = None
        self.transcricao_em_andamento = False
        self.arquivo_atual_index = 0
        self.cancelar_evento = threading.Event()
        self.transcricao_thread = None

        # Configurar interface
        self.setup_ui()

    def setup_ui(self):
        """Configura todos os elementos da interface"""

        # Frame principal com padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configurar peso das linhas e colunas
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # === Seção de seleção de arquivos ===
        ttk.Label(main_frame, text="Arquivos:", font=("Arial", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 5)
        )

        self.label_arquivos = ttk.Label(main_frame, text="Nenhum arquivo selecionado",
                                       foreground="gray")
        self.label_arquivos.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))

        ttk.Button(main_frame, text="Selecionar Arquivos",
                  command=self.selecionar_arquivos).grid(row=0, column=2, padx=(10, 0))

        # === Seção de pasta de saída ===
        ttk.Label(main_frame, text="Pasta de Saída:", font=("Arial", 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, pady=(10, 5)
        )

        self.label_pasta_saida = ttk.Label(main_frame, text="Mesma pasta dos arquivos",
                                          foreground="gray")
        self.label_pasta_saida.grid(row=1, column=1, sticky=tk.W, padx=(10, 0))

        ttk.Button(main_frame, text="Escolher Pasta",
                  command=self.selecionar_pasta_saida).grid(row=1, column=2, padx=(10, 0))

        # === Seção de configurações ===
        config_frame = ttk.LabelFrame(main_frame, text="Configurações", padding="10")
        config_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        # Modelo Whisper
        modelo_frame = ttk.Frame(config_frame)
        modelo_frame.grid(row=0, column=0, columnspan=3, sticky=tk.W)

        ttk.Label(modelo_frame, text="Modelo:").grid(row=0, column=0, sticky=tk.W)
        self.var_modelo = tk.StringVar(value="medium")
        self.combo_modelo = ttk.Combobox(modelo_frame, textvariable=self.var_modelo,
                                         values=["tiny", "base", "small", "medium"],
                                         state="readonly", width=15)
        self.combo_modelo.grid(row=0, column=1, padx=(10, 0), sticky=tk.W)

        # === Seção de status ===
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        self.label_status = ttk.Label(status_frame, text="Pronto", foreground="green")
        self.label_status.grid(row=0, column=0, sticky=tk.W)

        # === Botões de ação ===
        botoes_frame = ttk.Frame(main_frame)
        botoes_frame.grid(row=4, column=0, columnspan=3, pady=10)

        self.btn_transcrever = ttk.Button(botoes_frame, text="Transcrever",
                                          command=self.iniciar_transcricao,
                                          state="disabled")
        self.btn_transcrever.grid(row=0, column=0, padx=5)

    def selecionar_arquivos(self):
        """Abre diálogo para seleção de múltiplos arquivos de áudio/vídeo"""
        tipos_arquivo = [
            ("Arquivos de mídia", "*.mp3 *.wav *.m4a *.flac *.ogg *.mp4 *.mkv *.mov *.avi *.webm"),
            ("Todos os arquivos", "*.*")
        ]

        arquivos = filedialog.askopenfilenames(
            title="Selecionar arquivos de áudio ou vídeo",
            filetypes=tipos_arquivo
        )

        if arquivos:
            self.arquivos_selecionados = [Path(arquivo) for arquivo in arquivos]
            nome_exibido = f"{len(self.arquivos_selecionados)} arquivos selecionados"
            self.label_arquivos.config(text=nome_exibido, foreground="black")
            self.btn_transcrever.config(state="normal")

    def selecionar_pasta_saida(self):
        """Abre diálogo para seleção da pasta de saída"""
        pasta = filedialog.askdirectory(title="Selecionar pasta para salvar as transcrições")
        if pasta:
            self.pasta_saida = Path(pasta)
            self.label_pasta_saida.config(text=str(self.pasta_saida), foreground="black")

    def iniciar_transcricao(self):
        """Inicia o processo de transcrição"""
        if not self.arquivos_selecionados:
            messagebox.showwarning("Atenção", "Selecione pelo menos um arquivo primeiro!")
            return

        messagebox.showinfo("Whisper", "Funcionalidade de transcrição será implementada em breve!")

def main():
    """Função principal para executar a aplicação"""
    print(f"WhisperPGE v{APP_VERSION} - Iniciando...")

    try:
        # Check if already running
        if is_already_running():
            print("WhisperPGE já está em execução. Fechando esta instância.")
            messagebox.showinfo("WhisperPGE", "WhisperPGE já está em execução!")
            return

        # Create instance lock
        if not create_instance_lock():
            print("Falha ao criar lock de instância.")
            return

        # Check for updates first (only if not dev version and update libraries available)
        if APP_VERSION != "dev" and UPDATE_AVAILABLE:
            update_info = check_for_updates()
            if update_info.get("available"):
                should_update = show_update_dialog(update_info)
                if should_update:
                    print("Iniciando processo de atualização...")
                    if download_and_install_update(update_info["release_data"]):
                        print("Atualização iniciada. Fechando aplicação atual.")
                        remove_instance_lock()
                        return
                    else:
                        print("Falha na atualização. Continuando com versão atual.")

        # Check dependencies
        has_deps = check_dependencies_simple()
        print(f"Dependências disponíveis: {has_deps}")

        if not has_deps:
            print("Instalando dependências...")
            success = install_dependencies()
            if not success:
                print("Instalação falhou")
                remove_instance_lock()
                return

        print("Iniciando aplicação...")

        # Run the app
        root = tk.Tk()
        app = WhisperTranscriber(root)

        # Set up cleanup on window close
        def on_closing():
            remove_instance_lock()
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()

    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()
        remove_instance_lock()

if __name__ == "__main__":
    main()