CREATE TABLE app_migrations(version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE users(
 id BIGSERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS'),
 role TEXT NOT NULL DEFAULT 'user',token_version INTEGER NOT NULL DEFAULT 0,
 disabled INTEGER NOT NULL DEFAULT 0,phone TEXT,nickname TEXT NOT NULL DEFAULT '',bio TEXT NOT NULL DEFAULT '',avatar_id TEXT NOT NULL DEFAULT '');
CREATE UNIQUE INDEX users_phone ON users(phone) WHERE phone IS NOT NULL;
CREATE TABLE community_migrations(version INTEGER PRIMARY KEY);
CREATE TABLE posts(
 id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,category TEXT NOT NULL,tags TEXT NOT NULL,images TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'published',reason TEXT NOT NULL DEFAULT '',version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
 updated_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
 request_key TEXT NOT NULL,payload_hash TEXT NOT NULL,UNIQUE(user_id,request_key));
CREATE INDEX posts_feed ON posts(status,id DESC);
CREATE INDEX posts_category ON posts(status,category,id DESC);
CREATE INDEX posts_owner ON posts(user_id,id DESC);
CREATE TABLE media(id TEXT PRIMARY KEY,user_id BIGINT NOT NULL,ready INTEGER NOT NULL DEFAULT 0,touched_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS'));
CREATE TABLE moderation(id BIGSERIAL PRIMARY KEY,post_id BIGINT NOT NULL REFERENCES posts(id),actor_id BIGINT NOT NULL,action TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS'));
CREATE TABLE comments(id BIGSERIAL PRIMARY KEY,post_id BIGINT NOT NULL REFERENCES posts(id),user_id BIGINT NOT NULL,body TEXT NOT NULL,reply_to BIGINT REFERENCES comments(id),status TEXT NOT NULL DEFAULT 'published',reason TEXT NOT NULL DEFAULT '',version INTEGER NOT NULL DEFAULT 1,request_key TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),UNIQUE(user_id,request_key));
CREATE INDEX comments_post ON comments(post_id,id);
CREATE TABLE post_likes(post_id BIGINT NOT NULL REFERENCES posts(id),user_id BIGINT NOT NULL,PRIMARY KEY(post_id,user_id));
CREATE TABLE comment_moderation(id BIGSERIAL PRIMARY KEY,comment_id BIGINT NOT NULL REFERENCES comments(id),actor_id BIGINT NOT NULL,action TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS'));
CREATE TABLE reports(id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL,target_type TEXT NOT NULL,target_id BIGINT NOT NULL,post_id BIGINT NOT NULL REFERENCES posts(id),reason TEXT NOT NULL,snapshot TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',resolution TEXT,note TEXT,actor_id BIGINT,resolved_at TEXT,created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS'),UNIQUE(user_id,target_type,target_id));
CREATE INDEX reports_status ON reports(status,id DESC);
CREATE TABLE pets(id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL,name TEXT NOT NULL,species TEXT NOT NULL,breed TEXT NOT NULL DEFAULT '',sex TEXT NOT NULL DEFAULT 'unknown',birthday TEXT,bio TEXT NOT NULL DEFAULT '',photo_id TEXT,version INTEGER NOT NULL DEFAULT 1,deleted INTEGER NOT NULL DEFAULT 0,request_key TEXT NOT NULL,payload_hash TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),UNIQUE(user_id,request_key));
CREATE INDEX pets_owner ON pets(user_id,deleted,id);
CREATE TABLE post_pets(post_id BIGINT NOT NULL REFERENCES posts(id),pet_id BIGINT NOT NULL REFERENCES pets(id),PRIMARY KEY(post_id,pet_id));
CREATE INDEX pet_posts ON post_pets(pet_id,post_id);
CREATE TABLE chat_turns(seq BIGSERIAL PRIMARY KEY,user_id TEXT NOT NULL,thread_id TEXT NOT NULL,request_id TEXT NOT NULL,prompt TEXT NOT NULL,image_url TEXT,answer TEXT NOT NULL DEFAULT '',status TEXT NOT NULL,error TEXT NOT NULL DEFAULT '',UNIQUE(user_id,request_id));
CREATE INDEX chat_turns_thread ON chat_turns(user_id,thread_id,seq);
CREATE TABLE checkpoints(thread_id TEXT NOT NULL,checkpoint_ns TEXT NOT NULL DEFAULT '',checkpoint_id TEXT NOT NULL,parent_checkpoint_id TEXT,type TEXT,checkpoint BYTEA,metadata BYTEA,PRIMARY KEY(thread_id,checkpoint_ns,checkpoint_id));
CREATE TABLE writes(thread_id TEXT NOT NULL,checkpoint_ns TEXT NOT NULL DEFAULT '',checkpoint_id TEXT NOT NULL,task_id TEXT NOT NULL,idx INTEGER NOT NULL,channel TEXT,type TEXT,value BYTEA,PRIMARY KEY(thread_id,checkpoint_ns,checkpoint_id,task_id,idx));
CREATE TABLE data_imports(name TEXT PRIMARY KEY,source_fingerprint TEXT NOT NULL,report TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now());
INSERT INTO community_migrations(version) VALUES(1),(2),(3) ON CONFLICT DO NOTHING;
INSERT INTO app_migrations(version) VALUES(1) ON CONFLICT DO NOTHING;
