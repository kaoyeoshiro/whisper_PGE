# Whisper PGE

Aplicativo desktop para transcrever áudio e vídeo localmente usando Whisper e uma interface Tkinter. O projeto fornece executáveis Windows produzidos com PyInstaller e um atualizador escrito em Python que verifica novas versões publicadas no GitHub Releases.

## Pré-requisitos de desenvolvimento

- Windows 10 ou superior
- Python 3.10+ com `pip`
- FFmpeg acessível no `PATH`
- Dependências listadas em `requirements.txt`

Instale as dependências do projeto:

```
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Estrutura do projeto

```
.
├── app/
│   └── version.json
├── build.py            # script de build em Python
├── main.py             # aplicação principal
├── updater.py          # atualizador distribuído ao usuário final
├── build/              # artefatos gerados (WhisperPGE.exe, updater.exe, app/version.json)
├── requirements.txt
└── .github/workflows/release.yml
```

## Gerando os executáveis

Execute `python build.py`. O script garante que o PyInstaller esteja instalado, gera `WhisperPGE.exe` e `updater.exe` em modo `--onefile` (sem console) e copia `app/version.json` para `build/app/version.json`. O processo coleta todos os módulos e dados necessários de `torch`, `torchaudio`, `whisper` e dependências relacionadas, eliminando qualquer instalação dinâmica em tempo de execução. Os executáveis finais ficam em `build/`.

```
python build.py
```

Após o build, distribua os seguintes arquivos para a máquina do usuário:

- `WhisperPGE.exe` (aplicação principal com todas as dependências empacotadas)
- `updater.exe` (verificador de releases no GitHub)
- `app/version.json`

Mantenha-os na mesma pasta (por exemplo `C:\Program Files\WhisperPGE` ou `%USERPROFILE%\WhisperPGE`).

## Atualizações automáticas

- `updater.exe` registra-se automaticamente em `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` na primeira execução, garantindo que seja iniciado a cada login com a bandeira `--silent`.
- A cada execução o atualizador consulta `https://api.github.com/repos/kaoyeoshiro/whisper_PGE/releases/latest`, compara a versão local (`app/version.json`) com a versão remota (tag da release) e, somente se houver uma versão mais recente, exibe uma caixa de diálogo perguntando se o usuário deseja atualizar.
- Em caso afirmativo, o atualizador baixa o ativo `WhisperPGE.exe`, encerra instâncias em execução e substitui o binário local. Após sucesso, atualiza `app/version.json` e registra o evento em `%LOCALAPPDATA%\WhisperPGE\logs\updater.log`.

### Execução manual

Se quiser disparar a verificação manualmente, execute `updater.exe` (sem parâmetros) na pasta de instalação. Para execução silenciosa (sem mensagens quando não houver atualização), use `updater.exe --silent`.

### Remover o auto-start

Para desinstalar o atualizador automático, remova o valor `WhisperPGE-Updater` em `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (via Editor do Registro) ou apague o diretório de instalação inteiro.

## Publicando uma nova versão

1. Atualize o código e ajuste `app/version.json` com o novo número de versão.
2. Gere os executáveis com `python build.py` e teste localmente.
3. Faça commit/push das alterações.
4. Crie uma tag semântica `vX.Y.Z` e faça push da tag:
   ```
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
5. O workflow GitHub Actions (`.github/workflows/release.yml`) fará o build em um runner Windows usando `python build.py` e anexará `WhisperPGE.exe`, `updater.exe` e `app/version.json` à release.

## Solução de problemas

- **SmartScreen**: executáveis não assinados podem acionar o SmartScreen. Instrua o usuário a clicar em “Executar mesmo assim” se confiar na origem.
- **Erro ao baixar atualização**: verifique o log em `%LOCALAPPDATA%\WhisperPGE\logs\updater.log` e confirme conectividade com GitHub.
- **Permissões**: caso o registro no Run key falhe, execute `updater.exe` em uma sessão com privilégios suficientes.
- **FFmpeg ausente**: instale o FFmpeg e garanta que o executável esteja no `PATH` antes de usar `WhisperPGE.exe`.
