const bcrypt = require('bcrypt');

// Stored hashes use cost factor 12.
const COST_FACTOR = 12;

async function hashPassword(plain) {
  return await bcrypt.hash(plain, COST_FACTOR);
}

async function verifyPassword(plain, hash) {
  return await bcrypt.compare(plain, hash);
}

module.exports = { hashPassword, verifyPassword };
