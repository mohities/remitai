const {
  initiateDeveloperControlledWalletsClient
} = require('@circle-fin/developer-controlled-wallets')


const CIRCLE_API_KEY  = 'TEST_API_KEY:76b7fb5c6a56baaf5aed9e465426e556:68ae3abf14c66accaf2403888738a67f'
const ENTITY_SECRET   = 'ae93db7c6b93f7c063faf5768f54c97b20bbb2458d4125cb5cc671ae3e8df88d'
const WALLET_ID      = 'dcabbd15-57eb-5ad3-ab24-4df8f2fa36b3'

async function main() {
  const client = initiateDeveloperControlledWalletsClient({
    apiKey: CIRCLE_API_KEY,
    entitySecret: ENTITY_SECRET
  })

  const response = await client.getWallet({ id: WALLET_ID })
  console.log('Wallet details:')
  console.log(JSON.stringify(response.data, null, 2))
}

main().catch(console.error)


AccountEndpoint=https://cognizantremitai.documents.azure.com:443/;AccountKey=6riHJmo742jpZRN1voWfHroSYcSZcY9zdhmYEeBqvYoiVFyFhsF5DtRI1cPdJ2NgzTQ42gx6SXd6ACDbRdTJOg==;
