
# RemitAI — Stablecoin Remittance Co-pilot

AI-powered multilingual remittance agent helping migrant workers 
send money home using USDC stablecoins.

## The problem
200M+ migrant workers pay 6.5% average fees on remittances.
$40B extracted annually from the world's most vulnerable workers.

## The solution
Voice + chat AI agent. Multilingual. Stablecoin rails.
Fee: under 0.5%. Delivery: under 60 seconds.

## Tech stack
- Azure AI Foundry (agent orchestration)
- Azure OpenAI GPT-4o (agent brain)
- Azure AI Speech (voice input/output)
- Azure Translator (multilingual)
- Azure Functions (payment logic)
- Azure Communication Services (SMS)
- Azure Cosmos DB (transaction history)
- Circle USDC API (stablecoin transfer)

## Azure Resource Group
cognizant_remitai_hackathon-rg

## Setup
See docs/azure-resources.md for full provisioning guide.
Copy .env.example to .env and fill in your keys.