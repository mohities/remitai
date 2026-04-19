const {
  initiateDeveloperControlledWalletsClient
} = require('@circle-fin/developer-controlled-wallets')

const CIRCLE_API_KEY  = 'TEST_API_KEY:76b7fb5c6a56baaf5aed9e465426e556:68ae3abf14c66accaf2403888738a67f'
const ENTITY_SECRET   = 'ae93db7c6b93f7c063faf5768f54c97b20bbb2458d4125cb5cc671ae3e8df88d'

async function main() {
  const client = initiateDeveloperControlledWalletsClient({
    apiKey: CIRCLE_API_KEY,
    entitySecret: ENTITY_SECRET
  })

  const ciphertext = await client.generateEntitySecretCiphertext()
  console.log(`\nEntity secret ciphertext (${ciphertext.length} chars):`)
  console.log(ciphertext)
  console.log('\nAdd this to local.settings.json as CIRCLE_ENTITY_SECRET_CIPHERTEXT')
}

main().catch(console.error)