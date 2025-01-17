db = new Mongo().getDB("xdb");
db.createCollection('tweets', { capped: false });
db.createCollection('comments', { capped: false });
db.createCollection('attachments', { capped: false });