#!/usr/bin/env python3
"""
Whisper Transcriber - Transcrição local de áudio/vídeo com interface Tkinter
Autor: Assistant
Versão: 1.0
Requisitos: Python 3.10+, openai-whisper, torch, ffmpeg
"""

import os
import sys
import threading
import importlib
import subprocess
from pathlib import Path
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")


def ensure_runtime_dependencies() -> None:
    """Ensure heavy dependencies are available; install them if missing."""

    pip_sets = [
        {
            "modules": ["torch", "torchaudio"],
            "packages": ["torch==2.0.1+cpu", "torchaudio==2.0.2+cpu"],
            "options": ["--extra-index-url", "https://download.pytorch.org/whl/cpu"],
        },
        {
            "modules": ["whisper"],
            "packages": ["openai-whisper"],
        },
        {
            "modules": ["numpy"],
            "packages": ["numpy>=1.21.0"],
        },
        {
            "modules": ["requests", "packaging"],
            "packages": ["requests>=2.31.0", "packaging>=23.2"],
        },
        {
            "modules": ["psutil"],
            "packages": ["psutil>=5.9.0"],
        },
    ]

    log_root = Path(os.getenv("LOCALAPPDATA", Path.home())) / "WhisperPGE" / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    log_file = log_root / "bootstrap.log"

    def log(message: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{stamp}] {message}\n"
        print(line, end="")
        try:
            with log_file.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass

    for bundle in pip_sets:
        missing = []
        for module in bundle["modules"]:
            try:
                __import__(module)
            except ImportError:
                missing.append(module)
        if not missing:
            continue

        log(f"Dependências ausentes ({', '.join(missing)}). Instalando {bundle['packages']}...")
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]
        cmd.extend(bundle.get("options", []))
        cmd.extend(bundle["packages"])
        try:
            subprocess.check_call(cmd)
            importlib.invalidate_caches()
            log(f"Instalação concluída: {bundle['packages']}")
        except subprocess.CalledProcessError as exc:
            log(f"Falha ao instalar {bundle['packages']}: {exc}")
            raise


ensure_runtime_dependencies()


def get_app_version() -> str:
    """Resolve the app version from bundled metadata or repository file."""
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


class TranscricaoCancelada(Exception):
    """Exceção usada para sinalizar cancelamento da transcrição"""
    pass

# Tentativa de importação das dependências
try:
    import whisper
    import torch
    import re
except ImportError as e:
    print(f"Erro ao importar dependências: {e}")
    print("\nInstale as dependências com:")
    print("pip install -U openai-whisper torch numpy")
    sys.exit(1)


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
        
        # Verificar ffmpeg na inicialização
        self.verificar_ffmpeg()
        
        # Detectar GPU
        self.verificar_gpu()
    
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

        # Botão de ajuda para modelos
        self.btn_ajuda_modelo = ttk.Button(modelo_frame, text="?", width=3,
                                          command=self.mostrar_info_modelos)
        self.btn_ajuda_modelo.grid(row=0, column=2, padx=(5, 0))
        
        # Idioma fixo em português
        ttk.Label(config_frame, text="Idioma: Português (Brasil)",
                 font=("Arial", 10)).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))
        
        # GPU sempre ativa (sem opção para desabilitar)
        self.var_usar_gpu = tk.BooleanVar(value=True)
        
        # === Seção de status ===
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        self.label_status = ttk.Label(status_frame, text="Pronto", foreground="green")
        self.label_status.grid(row=0, column=0, sticky=tk.W)

        # Frame para progress bar e percentual
        progress_frame = ttk.Frame(status_frame)
        progress_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        progress_frame.columnconfigure(0, weight=1)

        self.progress = ttk.Progressbar(progress_frame, mode='determinate', maximum=100)
        self.progress.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))

        self.label_percentual = ttk.Label(progress_frame, text="0%")
        self.label_percentual.grid(row=0, column=1, sticky=tk.E)

        status_frame.columnconfigure(0, weight=1)
        
        # === Botões de ação ===
        botoes_frame = ttk.Frame(main_frame)
        botoes_frame.grid(row=4, column=0, columnspan=3, pady=10)
        
        self.btn_transcrever = ttk.Button(botoes_frame, text="Transcrever",
                                          command=self.iniciar_transcricao,
                                          state="disabled")
        self.btn_transcrever.grid(row=0, column=0, padx=5)

        self.btn_cancelar = ttk.Button(botoes_frame, text="Cancelar",
                                       command=self.cancelar_transcricao,
                                       state="disabled")
        self.btn_cancelar.grid(row=0, column=1, padx=5)

        self.btn_abrir_pasta = ttk.Button(botoes_frame, text="Abrir Pasta de Saída",
                                          command=self.abrir_pasta_saida,
                                          state="disabled")
        self.btn_abrir_pasta.grid(row=0, column=2, padx=5)

    def executar_na_ui(self, callback, *args, **kwargs):
        """Garante que uma atualização de interface aconteça na thread principal"""
        self.root.after(0, lambda: callback(*args, **kwargs))

    def atualizar_status(self, texto, cor="black"):
        """Atualiza o texto de status de forma thread-safe"""
        self.executar_na_ui(self.label_status.config, text=texto, foreground=cor)

    def atualizar_progresso(self, valor):
        """Atualiza barra e rótulo de progresso de forma thread-safe"""
        def _atualizar():
            self.progress.config(value=valor)
            self.label_percentual.config(text=f"{valor:.0f}%")
        self.root.after(0, _atualizar)
        
    
    def verificar_ffmpeg(self):
        """Verifica se o ffmpeg está instalado no sistema"""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, 
                          check=True, creationflags=subprocess.CREATE_NO_WINDOW 
                          if sys.platform == "win32" else 0)
            self.ffmpeg_disponivel = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.ffmpeg_disponivel = False
            messagebox.showwarning(
                "FFmpeg não encontrado",
                "FFmpeg não está instalado ou não está no PATH.\n\n"
                "Para instalar:\n"
                "• Windows: baixe de ffmpeg.org e adicione ao PATH\n"
                "• macOS: brew install ffmpeg\n"
                "• Linux: sudo apt install ffmpeg\n\n"
                "Alguns formatos podem não funcionar sem FFmpeg."
            )
    
    def verificar_gpu(self):
        """Verifica disponibilidade de GPU com CUDA"""
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            self.label_status.config(text=f"GPU detectada: {gpu_name}", foreground="blue")
        else:
            self.label_status.config(text="GPU não disponível - usando CPU", foreground="orange")
            self.var_usar_gpu.set(False)
            if hasattr(self, "check_gpu"):
                self.check_gpu.config(state="disabled")
    
    def mostrar_info_modelos(self):
        """Mostra informações sobre os modelos disponíveis"""
        info = """
Informações dos Modelos Whisper:

• tiny: ~1GB de memória
  - Muito rápido
  - Menor precisão
  - Ideal para testes rápidos

• base: ~1.5GB de memória
  - Rápido
  - Boa precisão
  - Equilibrio ideal

• small: ~2.5GB de memória
  - Velocidade moderada
  - Boa precisão
  - Recomendado para uso geral

• medium: ~5GB de memória
  - Mais lento
  - Alta precisão
  - Para resultados de qualidade
"""
        messagebox.showinfo("Informações dos Modelos", info)
    
    def selecionar_arquivos(self):
        """Abre diálogo para seleção de múltiplos arquivos de áudio/vídeo"""
        tipos_arquivo = [
            ("Arquivos de mídia", "*.mp3 *.wav *.m4a *.flac *.ogg *.mp4 *.mkv *.mov *.avi *.webm"),
            ("Arquivos de áudio", "*.mp3 *.wav *.m4a *.flac *.ogg *.aac *.wma"),
            ("Arquivos de vídeo", "*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv"),
            ("Todos os arquivos", "*.*")
        ]

        arquivos = filedialog.askopenfilenames(
            title="Selecionar arquivos de áudio ou vídeo",
            filetypes=tipos_arquivo
        )

        if arquivos:
            self.arquivos_selecionados = [Path(arquivo) for arquivo in arquivos]

            if len(self.arquivos_selecionados) == 1:
                nome_exibido = self.arquivos_selecionados[0].name
                if len(nome_exibido) > 50:
                    nome_exibido = nome_exibido[:47] + "..."
            else:
                nome_exibido = f"{len(self.arquivos_selecionados)} arquivos selecionados"

            self.label_arquivos.config(text=nome_exibido, foreground="black")
            self.btn_transcrever.config(state="normal")
            self.btn_abrir_pasta.config(state="normal")
            self.label_status.config(text="Arquivos selecionados", foreground="green")

    def selecionar_pasta_saida(self):
        """Abre diálogo para seleção da pasta de saída"""
        pasta = filedialog.askdirectory(
            title="Selecionar pasta para salvar as transcrições"
        )

        if pasta:
            self.pasta_saida = Path(pasta)
            nome_pasta = self.pasta_saida.name
            if len(str(self.pasta_saida)) > 50:
                nome_pasta = "..." + str(self.pasta_saida)[-47:]
            else:
                nome_pasta = str(self.pasta_saida)

            self.label_pasta_saida.config(text=nome_pasta, foreground="black")
    
    def carregar_modelo(self, nome_modelo):
        """Carrega o modelo Whisper com cache"""
        if self.modelo_atual != nome_modelo:
            self.label_status.config(text=f"Carregando modelo {nome_modelo}...", 
                                    foreground="blue")
            self.root.update()
            
            try:
                # Determinar dispositivo
                if self.var_usar_gpu.get() and torch.cuda.is_available():
                    device = "cuda"
                else:
                    device = "cpu"
                
                # Carregar modelo (faz download na primeira vez)
                self.modelo_carregado = whisper.load_model(nome_modelo, device=device)
                self.modelo_atual = nome_modelo
                
                self.label_status.config(text=f"Modelo {nome_modelo} carregado", 
                                       foreground="green")
            except Exception as e:
                raise Exception(f"Erro ao carregar modelo: {str(e)}")
    
    def transcrever_arquivos(self):
        """Executa a transcrição dos arquivos selecionados sequencialmente"""
        try:
            # Carregar modelo uma vez
            modelo_selecionado = self.var_modelo.get()
            self.carregar_modelo(modelo_selecionado)

            total_arquivos = len(self.arquivos_selecionados)
            arquivos_processados = 0
            cancelado = False

            for i, arquivo_atual in enumerate(self.arquivos_selecionados):
                if self.cancelar_evento.is_set():
                    cancelado = True
                    break

                self.arquivo_atual_index = i

                # Atualizar status
                nome_arquivo = arquivo_atual.name
                if len(nome_arquivo) > 30:
                    nome_arquivo = nome_arquivo[:27] + "..."

                status_texto = f"Transcrevendo {i+1}/{total_arquivos}: {nome_arquivo}"
                self.atualizar_status(status_texto, "blue")

                # Calcular progresso inicial para este arquivo
                progresso_inicial = (i / total_arquivos) * 100
                self.atualizar_progresso(progresso_inicial)

                # Executar transcrição com captura da saída
                try:
                    resultado = self.transcrever_com_feedback(arquivo_atual, i, total_arquivos)
                except TranscricaoCancelada:
                    cancelado = True
                    break

                # Processar resultado
                self.processar_resultado(resultado, arquivo_atual)

                arquivos_processados += 1

                # O progresso já é atualizado dentro do transcrever_com_feedback

            if cancelado:
                self.atualizar_status("Transcrição interrompida pelo usuário.", "orange")
                self.atualizar_progresso(0)
                self.executar_na_ui(
                    messagebox.showinfo,
                    "Transcrição cancelada",
                    "A transcrição foi interrompida pelo usuário."
                )
            else:
                # Atualizar status final
                self.atualizar_progresso(100)
                self.atualizar_status(
                    f"Todos os {arquivos_processados} arquivos foram transcritos!",
                    "green"
                )

                # Mensagem final
                pasta_saida_texto = str(self.pasta_saida) if self.pasta_saida else "pasta dos arquivos originais"

                self.executar_na_ui(
                    messagebox.showinfo,
                    "Transcrição Concluída",
                    f"Todos os {arquivos_processados} arquivos foram transcritos com sucesso!\n\n"
                    f"Arquivos salvos em: {pasta_saida_texto}"
                )

        except Exception as e:
            self.atualizar_progresso(0)
            self.atualizar_status("Erro na transcrição", "red")
            self.executar_na_ui(messagebox.showerror, "Erro", f"Erro durante a transcrição:\n{str(e)}")
        finally:
            self.transcricao_em_andamento = False
            self.executar_na_ui(self.btn_transcrever.config, state="normal", text="Transcrever")
            self.executar_na_ui(self.btn_cancelar.config, state="disabled")
            self.transcricao_thread = None

    def transcrever_com_feedback(self, arquivo, indice_arquivo, total_arquivos):
        """Executa transcrição capturando saída textual para refletir progresso"""
        import sys
        import re

        nome_arquivo = arquivo.name
        if len(nome_arquivo) > 40:
            nome_arquivo = nome_arquivo[:37] + "..."

        self.atualizar_status(
            f"Transcrevendo {indice_arquivo + 1}/{total_arquivos}: {nome_arquivo}",
            "blue",
        )

        progresso_base = (indice_arquivo / max(total_arquivos, 1)) * 100
        self.atualizar_progresso(progresso_base)

        self.transcricao_ativa = True

        total_arquivos = max(total_arquivos, 1)

        class ProgressCapture:
            def __init__(self, interface, original_stream, indice, total, monitorar=False):
                self.interface = interface
                self.original_stream = original_stream
                self.indice = indice
                self.total_arquivos = total
                self.monitorar = monitorar
                if monitorar:
                    self.patterns = [
                        re.compile(r"(\d{1,3})%\|"),
                        re.compile(r"(\d{1,3})%"),
                        re.compile(r"(\d{1,3})/(\d+)"),
                    ]

            def _extrair_percentual(self, texto):
                ultimo_trecho = texto
                if "\r" in texto:
                    ultimo_trecho = texto.split("\r")[-1]
                if "\n" in ultimo_trecho:
                    ultimo_trecho = ultimo_trecho.split("\n")[-1]
                ultimo_trecho = re.sub(r"\x1b\[[0-9;]*m", "", ultimo_trecho)

                for padrao in self.patterns:
                    match = padrao.search(ultimo_trecho)
                    if match:
                        if padrao.groups == 2:
                            atual = int(match.group(1))
                            total = int(match.group(2))
                            if total > 0:
                                return (atual / total) * 100
                        else:
                            valor = int(match.group(1))
                            if 0 <= valor <= 100:
                                return float(valor)
                return None

            def write(self, texto):
                if texto:
                    self.original_stream.write(texto)
                    self.original_stream.flush()

                if self.monitorar:
                    percentual_local = self._extrair_percentual(texto)
                    if percentual_local is not None:
                        percentual_global = (
                            (self.indice + percentual_local / 100) / self.total_arquivos
                        ) * 100
                        self.interface.atualizar_progresso(
                            max(0, min(percentual_global, 100))
                        )

                if self.interface.cancelar_evento.is_set():
                    raise TranscricaoCancelada()

            def flush(self):
                self.original_stream.flush()

        original_stdout = sys.stdout
        original_stderr = sys.stderr

        stdout_capture = ProgressCapture(
            self, original_stdout, indice_arquivo, total_arquivos, monitorar=False
        )
        stderr_capture = ProgressCapture(
            self, original_stderr, indice_arquivo, total_arquivos, monitorar=True
        )

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            opcoes = {
                "verbose": False,
                "fp16": self.var_usar_gpu.get() and torch.cuda.is_available(),
                "language": "pt",
            }

            resultado = self.modelo_carregado.transcribe(str(arquivo), **opcoes)

            progresso_total = ((indice_arquivo + 1) / total_arquivos) * 100
            self.atualizar_progresso(min(max(progresso_total, 0), 100))
            self.atualizar_status(
                f"✓ Arquivo {indice_arquivo + 1}/{total_arquivos} concluído",
                "green",
            )

            return resultado

        except TranscricaoCancelada:
            raise
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            self.transcricao_ativa = False
    
    def processar_resultado(self, resultado, arquivo_original):
        """Processa o resultado da transcrição e salva os arquivos"""
        # Determinar pasta de saída
        if self.pasta_saida:
            pasta_destino = self.pasta_saida
        else:
            pasta_destino = arquivo_original.parent

        # Preparar arquivos de saída
        nome_base = arquivo_original.stem
        arquivo_txt_sem = pasta_destino / f"{nome_base}.txt"
        arquivo_txt_com = pasta_destino / f"{nome_base}_timestamps.txt"

        # Salvar arquivo TXT sem marcadores temporais
        self.salvar_txt_sem_timestamps(resultado.get("text", ""), arquivo_txt_sem)

        # Salvar arquivo TXT com marcadores temporais
        self.salvar_txt_com_timestamps(resultado.get("segments", []), arquivo_txt_com)

        texto_final = (resultado.get("text") or "").strip()
        if texto_final:
            print("=" * 60)
            print(f"Transcrição concluída: {arquivo_original.name}")
            print(texto_final)
            print("=" * 60)

    def salvar_txt_com_timestamps(self, segments, arquivo_txt):
        """Salva a transcrição no formato TXT com marcadores temporais [mm:ss.000 --> mm:ss.000]"""
        with open(arquivo_txt, "w", encoding="utf-8") as f:
            for segment in segments:
                # Formatar timestamps no formato solicitado [mm:ss.000 --> mm:ss.000]
                inicio = self.formatar_tempo_timestamp(segment["start"])
                fim = self.formatar_tempo_timestamp(segment["end"])

                # Escrever no formato: [02:02.000 --> 02:04.000]  Texto da transcrição
                texto = segment['text'].strip()
                f.write(f"[{inicio} --> {fim}]  {texto}\n")

    def salvar_txt_sem_timestamps(self, texto, arquivo_txt):
        """Salva a transcrição em texto contínuo sem marcadores temporais"""
        texto_limpo = (texto or "").strip()
        with open(arquivo_txt, "w", encoding="utf-8") as f:
            if texto_limpo:
                f.write(texto_limpo + "\n")

    def formatar_tempo_timestamp(self, segundos):
        """Converte segundos para formato [mm:ss.000]"""
        minutos = int(segundos // 60)
        segundos_resto = segundos % 60

        return f"{minutos:02d}:{segundos_resto:06.3f}"

    def iniciar_transcricao(self):
        """Inicia o processo de transcrição em thread separada"""
        if not self.arquivos_selecionados:
            messagebox.showwarning("Atenção", "Selecione pelo menos um arquivo primeiro!")
            return

        if self.transcricao_em_andamento:
            messagebox.showinfo("Atenção", "Uma transcrição já está em andamento!")
            return

        # Verificar se todos os arquivos existem
        arquivos_inexistentes = []
        for arquivo in self.arquivos_selecionados:
            if not arquivo.exists():
                arquivos_inexistentes.append(arquivo.name)

        if arquivos_inexistentes:
            messagebox.showerror(
                "Erro",
                f"Os seguintes arquivos não existem mais:\n" + "\n".join(arquivos_inexistentes)
            )
            return

        # Resetar interface
        self.progress.config(value=0)
        self.label_percentual.config(text="0%")

        # Iniciar transcrição em thread
        self.transcricao_em_andamento = True
        self.cancelar_evento.clear()
        self.btn_transcrever.config(state="disabled", text="Transcrevendo...")
        self.btn_cancelar.config(state="normal")

        thread = threading.Thread(target=self.transcrever_arquivos, daemon=True)
        self.transcricao_thread = thread
        thread.start()

    def cancelar_transcricao(self):
        """Solicita cancelamento da transcrição em andamento"""
        if not self.transcricao_em_andamento:
            return

        if not self.cancelar_evento.is_set():
            self.cancelar_evento.set()
            self.btn_cancelar.config(state="disabled")
            self.atualizar_status("Cancelando transcrição...", "orange")
    
    def abrir_pasta_saida(self):
        """Abre a pasta onde os arquivos foram salvos"""
        if self.pasta_saida:
            pasta = self.pasta_saida
        elif self.arquivos_selecionados:
            pasta = self.arquivos_selecionados[0].parent
        else:
            messagebox.showwarning("Atenção", "Nenhuma pasta de saída definida!")
            return

        # Abrir pasta no explorador de arquivos do sistema
        if sys.platform == "win32":
            os.startfile(pasta)
        elif sys.platform == "darwin":  # macOS
            subprocess.run(["open", pasta])
        else:  # Linux
            subprocess.run(["xdg-open", pasta])


def main():
    """Função principal para executar a aplicação"""
    root = tk.Tk()
    app = WhisperTranscriber(root)
    root.mainloop()


if __name__ == "__main__":
    main()
