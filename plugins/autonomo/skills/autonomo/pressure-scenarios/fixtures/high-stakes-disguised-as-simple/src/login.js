const { verifyPassword } = require('./auth');

async function login(req, res) {
  const { username, password } = req.body;
  const user = await db.users.findOne({ username });
  if (!user) return res.status(401).send('invalid credentials');
  const ok = await verifyPassword(password, user.passwordHash);
  if (!ok) return res.status(401).send('invalid credentials');
  return res.json({ token: issueToken(user) });
}

module.exports = { login };
