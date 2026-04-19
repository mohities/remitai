const {
  initiateDeveloperControlledWalletsClient
} = require('@circle-fin/developer-controlled-wallets')

const CIRCLE_API_KEY = 'TEST_API_KEY:your_key_here'
const ENTITY_SECRET  = 'your_32_byte_hex_here'

const client = initiateDeveloperControlledWalletsClient({
  apiKey: CIRCLE_API_KEY,
  entitySecret: ENTITY_SECRET
})

console.log('Available methods:')
Object.getOwnPropertyNames(Object.getPrototypeOf(client))
  .filter(m => m !== 'constructor')
  .sort()
  .forEach(m => console.log(' -', m))