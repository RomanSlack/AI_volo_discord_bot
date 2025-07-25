
# OpenNoteV2 - Professional Discord Transcription Bot

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.0+-blue.svg)](https://discordpy.readthedocs.io/)
[![OpenAI](https://img.shields.io/badge/OpenAI-Whisper-green.svg)](https://openai.com/research/whisper)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Discord bot that transcribes voice channels and generates AI-powered meeting summaries. Forked from [volo_discord_bot](https://github.com/joshinryz/volo_discord_bot).

## Features

- **Real-time Transcription**: Converts voice to text instantly during meetings
- **Multi-participant Support**: Handles multiple speakers simultaneously
- **Professional Output**: Generates clean, formatted transcriptions
- **PDF Export**: Creates professional PDF reports of transcribed sessions
- **Participant Mapping**: Identifies speakers by name for better organization
- **OpenAI Integration**: Uses state-of-the-art Whisper API for accuracy
- **Thread-safe Operations**: Reliable concurrent transcription handling

## Setup

To set up and run this Discord bot, follow these steps:

### Prerequisites

- Python 3.7 or higher.
- Discord bot token (see [Discord Developer Portal](https://discord.com/developers/applications)).
- `ffmpeg` installed and added to your system's PATH.

### Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/your-github-username/discord-transcription-bot.git
   cd discord-transcription-bot
   ```

2. **Create a Virtual Environment (optional but recommended):**

   ```bash
   python -m venv venv
   # Activate the virtual environment
   # On Windows: venv\Scripts\activate
   # On macOS/Linux: source venv/bin/activate
   ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**

   Create a `.env` file in the root directory and add your Discord bot token and guild ID:

   ```
   DISCORD_BOT_TOKEN=your_discord_bot_token
   GUILD_ID=your_guild_id
   PARTICIPANT_MAP_FILE_PATH=path_to_participant_map.yml
   TRANSCRIPTION_METHOD=openai
   OPENAI_API_KEY=your_openai_api_key
   ```

### Configuration

- Edit `participant_map.yml` to map Discord user IDs to participant names for better transcription identification
- Configure transcription method (local or OpenAI) via environment variables
- Adjust audio processing settings in the whisper sink configuration

## Usage

1. **Start the Bot:**

   ```bash
   python main.py
   ```

2. **Bot Commands:**

   - `/connect`: Connect to your voice channel
   - `/scribe`: Start transcribing the voice channel
   - `/stop`: Stop transcription and save results
   - `/disconnect`: Disconnect from the voice channel
   - `/summarize`: Generate AI summary and PDF report
   - `/help`: Show command help

## Use Cases

- **Business Meetings**: Record and transcribe team meetings, client calls, and presentations
- **Educational Sessions**: Capture lectures, seminars, and study group discussions
- **Remote Collaboration**: Document brainstorming sessions and project planning meetings
- **Legal/Compliance**: Maintain accurate records of important discussions

## Contributing

Contributions are welcome! Please follow the project's coding standards and submit pull requests for new features or improvements.

## License

[MIT License](LICENSE)

## Acknowledgments

- Powered by [OpenAI Whisper](https://openai.com/research/whisper) for professional-grade transcription
- Built with [Pycord](https://github.com/Pycord-Development/pycord) for Discord integration
- Thanks to the open-source community for their valuable contributions
