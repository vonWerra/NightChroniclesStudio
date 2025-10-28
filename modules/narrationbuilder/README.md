# narrationbuilder (NightChronicles module)

Purpose: Merge narration segments into a single final narrative using OpenAI (gpt-5, fallback gpt-4.1).

CLI
- python -m narrationbuilder --project-root <repo-root> --topic-id <slug> --episode-id 01 --lang CS
- Requires: OPENAI_API_KEY in env.

Outputs
- outputs/final/<topic>/<LANG>/episode_01/episode_01_final.txt
- prompt_pack.json, metrics.json, status.json

Environment
- GPT_MODEL (default: gpt-5)
- GPT_TEMPERATURE (default: 0.4)
