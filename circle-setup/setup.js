const {
  initiateDeveloperControlledWalletsClient,
  registerEntitySecretCiphertext
} = require('@circle-fin/developer-controlled-wallets')

const CIRCLE_API_KEY  = 'TEST_API_KEY:76b7fb5c6a56baaf5aed9e465426e556:68ae3abf14c66accaf2403888738a67f'
const ENTITY_SECRET   = 'ae93db7c6b93f7c063faf5768f54c97b20bbb2458d4125cb5cc671ae3e8df88d'

async function main() {

  console.log('Step 1 — Registering entity secret...')
  await registerEntitySecretCiphertext({
    apiKey: CIRCLE_API_KEY,
    entitySecret: ENTITY_SECRET,
    recoveryFileDownloadPath: './'
  })
  console.log('Entity secret registered. Check folder for recovery file.')

  console.log('\nStep 2 — Creating wallet set and wallet...')
  const client = initiateDeveloperControlledWalletsClient({
    apiKey: CIRCLE_API_KEY,
    entitySecret: ENTITY_SECRET
  })

  const walletSetResponse = await client.createWalletSet({
    name: 'RemitAI Hackathon Wallet Set'
  })
  const walletSetId = walletSetResponse.data?.walletSet?.id
  console.log(`Wallet Set ID: ${walletSetId}`)

  const walletsResponse = await client.createWallets({
    blockchains: ['ETH-SEPOLIA'],
    count: 1,
    walletSetId: walletSetId
  })
  const wallet = walletsResponse.data?.wallets[0]
  console.log(`Wallet ID:      ${wallet.id}`)
  console.log(`Wallet Address: ${wallet.address}`)
  console.log(`Blockchain:     ${wallet.blockchain}`)

  console.log('\n--- SAVE THESE VALUES ---')
  console.log(`CIRCLE_WALLET_SET_ID=${walletSetId}`)
  console.log(`CIRCLE_WALLET_ID=${wallet.id}`)
  console.log(`CIRCLE_WALLET_ADDRESS=${wallet.address}`)
  console.log('-------------------------')
}

main().catch(console.error)