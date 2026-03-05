# CLM-lite Onboarding Guide

## Prerequisites

- Docker and Docker Compose installed
- Git

## Quickstart

1. Clone the repository and enter the directory
2. Copy environment file:
   ```bash
   cp .env.example .env
   ```
3. Start the application:
   ```bash
   docker compose up --build
   ```
4. Open http://localhost:8000 in your browser
5. You will be redirected to the **Setup Wizard**

## Setup Wizard Walkthrough

### Step 1: Create Admin Account
- Enter your name, email, and a password (min 8 characters)
- This creates the first administrator who can manage all settings

### Step 2: AI Provider Configuration
- **Mock Mode** (default): No API key needed. Uses realistic placeholder text for document generation. Recommended for initial exploration.
- **Anthropic (Claude)**: Enter your Anthropic API key and select a model (default: `claude-sonnet-4-20250514`)
- **OpenRouter**: Enter your OpenRouter API key and model identifier
- Optionally configure a **fallback provider** for resilience

### Step 3: Integrations
- **Pipedrive CRM**: Toggle mock mode on/off. In mock mode, sample deals are provided. For real data, enter your Pipedrive API token.

### Step 4: Complete Setup
- Review your configuration and click "Launch CLM-lite"
- You'll be redirected to the dashboard

## Creating Your First Document

1. Navigate to **Deals** and select a deal (or sync from Pipedrive)
2. Go to **Documents** > **New Document**
3. Select a template and deal
4. Click **Generate** — the system will fill placeholders and generate AI content
5. Download the generated DOCX file

## Post-Setup Configuration

All settings can be changed later from **Admin > Settings** (visible only to admin users in the sidebar).

## Understanding Mock Mode

When mock mode is enabled:
- AI generation returns professional placeholder text
- Pipedrive returns sample deal data
- No external API calls are made
- This is the recommended mode for demos and development
