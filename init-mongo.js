// Read credentials from .secrets files
var username = fs.readFileSync('/docker-entrypoint-initdb.d/.secrets/mongodb_user.txt', 'utf8').trim();
var password = fs.readFileSync('/docker-entrypoint-initdb.d/.secrets/mongodb_pwd.txt', 'utf8').trim();

// Switch to admin database to create user
db = db.getSiblingDB('admin');

// Create user for xdb database
db.createUser({
  user: username,
  pwd: password,
  roles: [
    { role: "readWrite", db: "xdb" },
    { role: "dbAdmin", db: "xdb" }
  ]
});

// Switch to xdb database and create collections
db = db.getSiblingDB("xdb");
db.createCollection('tweets', { capped: false });
db.createCollection('comments', { capped: false });
db.createCollection('attachments', { capped: false });
db.createCollection('profile', { capped: false });