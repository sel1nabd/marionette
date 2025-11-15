# Marionette 🎭

LLM orchestration layer for CLI coding agents with Gemini-powered metacognitive supervision.

## Overview

Marionette watches interactions between users and coding agents, providing intelligent guidance and supervision using Google's Gemini models.

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and add your Google API key:

```bash
cp .env.example .env
```

## Usage

```bash
python main.py
```

## Project Structure

- `orchestrator/` - Core orchestration logic
- `examples/` - Example usage scenarios
- `tests/` - Test suite

## Requirements

- Python 3.8+
- Google Generative AI API key
