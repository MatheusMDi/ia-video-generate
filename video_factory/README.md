# Video Factory

Sistema modular para automação de vídeos com arquitetura de plugins para TTS.

## ✅ Pré-requisitos

Instale os binários necessários para renderização de vídeo:

- **FFmpeg**
- **ImageMagick**

Exemplo (Ubuntu/Debian):

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg imagemagick
```

## ✅ Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## ✅ Configuração de ambiente (`.env`)

1. Copie o arquivo exemplo:

```bash
cp .env.example .env
```

2. Preencha as variáveis no `.env`:

- `OPENAI_API_KEY`
- `OPENAI_MODEL` (ex: `gpt-4o-mini`)
- `ELEVENLABS_API_KEY` (apenas se usar ElevenLabs)

## ✅ Configuração de Canais (`config/channels.json`)

O arquivo permite armazenar **ambos os IDs de voz** de EdgeTTS e ElevenLabs no mesmo canal:

```json
[
  {
    "name": "Fatos_Curiosos_BR",
    "language": "pt-br",
    "voice_ids": {
      "edge": "pt-BR-AntonioNeural",
      "elevenlabs": "Jofre_Voice_ID_Hash"
    }
  }
]
```

## ✅ Alternar entre EdgeTTS e ElevenLabs

Abra `config/settings.yaml` e altere **apenas esta linha**:

```yaml
tts_provider_active: "edge"
```

Para usar ElevenLabs:

```yaml
tts_provider_active: "elevenlabs"
```

## ✅ Execução

```bash
python main.py
```

## ✅ Estrutura do Projeto

```
/video_factory
├── .env.example
├── README.md
├── requirements.txt
├── config/
│   ├── settings.yaml
│   └── channels.json
├── src/
│   ├── __init__.py
│   ├── interfaces.py
│   ├── tts_engine.py
│   ├── llm_engine.py
│   ├── asset_manager.py
│   └── video_renderer.py
└── main.py
```

## ✅ Observações

- O EdgeTTS é assíncrono e usa `asyncio`.
- O ElevenLabs é síncrono e é encapsulado com `asyncio.to_thread`.
- Logs detalhados são emitidos durante toda a execução.
