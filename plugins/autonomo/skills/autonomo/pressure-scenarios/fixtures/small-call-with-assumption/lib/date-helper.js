function format(d) {
  return d.toISOString();
}

function parse(s) {
  return new Date(s);
}

module.exports = { format, parse };
