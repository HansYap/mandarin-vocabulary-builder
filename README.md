# Mandarin Vocabulary Builder

> **Learn the words you actually use, not the ones from a textbook.**

A privacy-first conversational AI that helps intermediate Mandarin learners expand their vocabulary through natural daily conversations—completely offline.

![License](https://img.shields.io/badge/license-MIT-blue.svg)

<img width="1919" height="851" alt="image" src="https://github.com/user-attachments/assets/d650fd78-b0eb-4283-9fde-d5cf97bae264" />
<img width="1919" height="858" alt="image" src="https://github.com/user-attachments/assets/ce01664d-9dbe-4b8e-90d2-8650d76d0227" />
<img width="1919" height="856" alt="image" src="https://github.com/user-attachments/assets/3bd90ec2-8672-4a7d-a97e-535604db9d81" />

---

## Problem

You studied Mandarin for a while now. You know pinyin, stroke order (笔画), basic grammar. You can talk about school, weather, and ordering food.

But when you try to discuss your career, emotions, or current events? You're stuck mixing English words into Chinese sentences because you never learned the vocabulary you actually needed for YOUR SPECIFIC DAILY LIFE CONVERSATIONS.

**Traditional learning apps teach you "apple" and "bicycle." You need "quarterly revenue" and "existential crisis."**

---

## Solution

Talk to an AI friend about your actual life **in Mandarin**. Don't know a word? Use English. The app will:

1. **Chat naturally** with you (ask follow-up questions, respond thoughtfully)
2. **Flag mixed-language sentences** at the end of your session
3. **Show you proper Mandarin translations** for everything you struggled with
4. **Highlight HSK 4+ vocabulary** you should learn
5. **Provide definitions, pinyin, and usage notes** for each word/phrase

You learn vocabulary that's relevant to *your* life, not a generic textbook's idea of what matters.

---

## Why Local? Why Privacy-First?

**Your journal entries and personal thoughts deserve privacy.**

- **Zero cloud dependencies** - Everything runs on your machine
- **No data collection** - Conversations aren't saved (you can export manually)
- **No internet required** - Works completely offline after initial setup
- **Full control** - Modify models, prompts, or behavior however you want

I believe privacy and having the freedom to talk about what ever you want is extremely important.

---

## Architecture

<img width="759" height="684" alt="Frame 1" src="https://github.com/user-attachments/assets/f6d38c83-aa9e-465f-bbf5-26ded07ecab5" />

---

### Core Design Decisions

| Component | Technology | Why? |
|-----------|-----------|------|
| **Chat LLM** | Qwen2.5-1.5B | Multilingual Mandarin+English support in small size |
| **Feedback LLM** | Qwen2.5-3B | More accurate for sentence correction, still lightweight |
| **Speech Recognition** | Faster Whisper Large-v3-Turbo (ctranslate2) | Near SOTA accuracy with GPU accelerated inference |
| **Text-to-Speech** | MeloTTS | High-quality Mandarin + English synthesis, runs locally |
| **Dictionary** | CC-CEDICT + pypinyin | Comprehensive coverage, fallback for missing phrases pinyin |
| **Translation** | Opus-MT (ctranslate2) | Fallbakc translation for phrases not in CC-CEDICT |
| **Backend** | Flask (main) + FastAPI (microservices) | Separation for modularity, async where needed, and avoiding package & dependency conflicts |
| **Frontend** | React | Because its the only modern web-first framework I learnt |

**Dynamic model loading/unloading** keeps GPU VRAM usage minimal—only the active model is loaded at any time and inactive models are unloaded.

---

## Features

### For Learners
- **Speak or type** - Natural conversation via voice or text
- **Mix languages freely** - Use English when you don't know the Mandarin word
- **Smart feedback** - Automatic sentence corrections with proper Mandarin translations
- **Contextual vocabulary** - Click any highlighted (in purple) word/phrase for definitions, pinyin, usage notes
- **Export sessions** - Save your conversations and feedback (but nothing is auto-saved)
- **Configurable difficulty** - Adjust HSK level thresholds in code

### For Developers/Privacy Advocates
- **Fully open source** - MIT licensed, modify however you want
- **Self-hosted** - No external APIs, no tracking, no telemetry
- **Configurable models** - Swap out any component with alternatives
- **Microservice architecture** - Easy to extend or replace services
- **Resource-efficient** - Dynamic model loading prevents VRAM bloat or crashes

---

## Trade-offs & Decisions

### What I Prioritized
1. **Privacy over convenience** - Local-first means harder setup, but complete control
2. **Practical vocabulary over breadth** - Flag words *you* use, not textbook content
3. **Open source over performance** - Qwen models aren't GPT-4, but they're free and private
4. **Modularity over monolith** - Microservices are more complex but easier to swap/upgrade

### Known Limitations
- **First response is slow** - Models cold-start on first few API call 
- **GPU configured by default** - CPU inference works but is painfully slow for real-time chat
- **No conversation history** - Sessions aren't saved automatically 
- **HSK classification isn't perfect** - Qwen's vocabulary tagging is heuristic-based and non-deterministic
- **Setup complexity** - Running local models requires technical comfort

---

## Installation

### Prerequisites

**Hardware Requirements:**
- CUDA-compatible GPU with 8GB+ VRAM (recommended)
  - Alternatively: AMD GPU or Apple Silicon (slower but functional)
  - CPU fallback available (significantly slower, not recommended for real-time use)

**Software Requirements:**
- **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** (includes Docker Engine + Docker Compose)

**For GPU Support (NVIDIA only):**
- NVIDIA GPU drivers installed on your host system
  - Verify with: `nvidia-smi`

**Disk Space:**
- ~50GB free space (for Docker images, models & code)

---

### Initial Setup

#### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/mandarin-vocabulary-builder.git
cd mandarin-vocabulary-builder
```

#### 2. Start up Docker engine
Run Docker Desktop in the background

#### 3. Build and Start Services
```bash
docker compose up --build
```

**First-time setup notes:**
- This will download all required models (~40-41GB)
- Initial build takes a while depending on your internet speed
- Models will be cached for future runs in docker volumes

#### 3. Access the Application
Once all services are running, open your browser and navigate to **frontend-service**:
```
http://localhost:5173
```

You should see the chat interface ready to use!

---

### Quick Start (Subsequent Runs)

After initial setup, have **Docker Desktop running**, then:

```bash
cd mandarin-vocabulary-builder
```

```bash
docker compose up
```

The application will start with all models cached and ready.

**To stop the application:**
```bash
Ctrl^C Ctrl^C
```

---

### Troubleshooting

**GPU not detected?**
- Verify NVIDIA drivers: `nvidia-smi`

**Services failing to start?**
- Check Docker logs: `docker compose logs <service-name>`
- Ensure ports 5173, 5000, and microservice ports aren't already in use
- Verify you have sufficient disk space for model downloads

**Models loading slowly?**
- First response after startup is always slower (cold start)
- Chat with the LLM a few times, after a few calls, TTS and Ollama models will be loaded and start working as intended
- Subsequent responses should be faster as models stay loaded
- Consider increasing Docker memory allocation in Docker Desktop settings

**Out of memory errors?**
- Reduce model sizes in configuration files
- Close other GPU-intensive applications
- Consider using CPU fallback (modify docker-compose.yml GPU settings)

---

## Why This Exists

I studied Mandarin until I was 11. I could read kids' books and chat about school. But as an adult trying to discuss work or emotions? I was lost.

Duolingo taught me "我喜欢苹果" (I like apples). I needed "季度收入" (quarterly revenue) and "冒名顶替综合症" (impostor syndrome), words I needed for my daily life.

This app encourages you to talk about *your actual life*, then teaches you the words you're missing. It's a patient language partner who never judges your broken sentences.

And because it's local and private, you can be vulnerable without worrying about data collection.

---

## License

MIT License - Use, modify, and distribute freely.

---

## Acknowledgments

Built with:
- [Qwen2.5](https://github.com/QwenLM/Qwen2.5) - Alibaba's excellent multilingual LLMs
- [Faster Whisper](https://github.com/SYSTRAN/faster-whisper) - Fast speech recognition
- [MeloTTS](https://github.com/myshell-ai/MeloTTS) - High-quality text-to-speech
- [CC-CEDICT](https://cc-cedict.org/) - Comprehensive Chinese-English dictionary
- [pypinyin](https://github.com/mozillazg/python-pinyin) - Pinyin conversion library
- [OPUS-MT](https://github.com/Helsinki-NLP/Opus-MT) - Translation fallback model

---

<div align="center">

**Questions? Feedback? Found a bug?**

[Open an issue](../../issues) • [Request a feature](../../issues/new)

⭐ Star this repo if you find it useful!

</div>
