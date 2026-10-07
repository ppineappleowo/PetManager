from app.database.repositories.base import Repository


class PetsRepository(Repository):
    def __init__(self, database, lock):
        self.db = database
        self.lock = lock

    def get_pet(self, pet_id):
        return self.db.execute('SELECT * FROM pets WHERE id=? AND deleted=0', (pet_id,)).fetchone()

    def list_pets(self, user_id):
        return self.db.execute('SELECT id FROM pets WHERE user_id=? AND deleted=0 ORDER BY id DESC', (user_id,)).fetchall()

    def find_pet_request(self, user_id, request_key):
        return self.db.execute('SELECT * FROM pets WHERE user_id=? AND request_key=?', (user_id, request_key)).fetchone()

    def count_pets(self, user_id):
        return self.db.execute('SELECT COUNT(*) FROM pets WHERE user_id=? AND deleted=0', (user_id,)).fetchone()[0]

    def insert_pet(self, user_id, request_key, digest, values):
        return self.db.execute('INSERT INTO pets(name,species,breed,sex,birthday,bio,photo_id,user_id,request_key,payload_hash) VALUES(?,?,?,?,?,?,?,?,?,?)', (*values, user_id, request_key, digest)).lastrowid

    def update_pet(self, pet_id, values):
        return self.result(self.db.execute('UPDATE pets SET name=?,species=?,breed=?,sex=?,birthday=?,bio=?,photo_id=?,version=version+1 WHERE id=?', (*values, pet_id)))

    def touch_pet_media(self, user_id):
        return self.result(self.db.execute("UPDATE media SET touched_at=datetime('now') WHERE user_id=?", (user_id,)))

    def delete_pet(self, pet_id):
        return self.result(self.db.execute('UPDATE pets SET deleted=1,version=version+1 WHERE id=?', (pet_id,)))

    def bump_linked_post_versions(self, pet_id):
        return self.result(self.db.execute('UPDATE posts SET version=version+1 WHERE id IN (SELECT post_id FROM post_pets WHERE pet_id=?)', (pet_id,)))

    def remove_pet_links(self, pet_id):
        return self.result(self.db.execute('DELETE FROM post_pets WHERE pet_id=?', (pet_id,)))

    def touch_deleted_pet_media(self, user_id):
        return self.result(self.db.execute("UPDATE media SET touched_at=datetime('now') WHERE user_id=?", (user_id,)))

    def list_post_pets(self, post_id):
        return self.db.execute('SELECT pp.pet_id FROM post_pets pp JOIN pets p ON p.id=pp.pet_id WHERE pp.post_id=? AND p.deleted=0 AND p.hidden=0 ORDER BY pp.pet_id', (post_id,)).fetchall()

    def moderate(self, pet_id, hidden):
        self.db.execute('UPDATE pets SET hidden=?,version=version+1 WHERE id=?',(int(hidden),pet_id))

    def admin_list(self, before, limit):
        where, args = ('id<?',[before]) if before else ('1=1',[])
        rows = self.db.execute('SELECT * FROM pets WHERE deleted=0 AND '+where+' ORDER BY id DESC LIMIT ?',[*args,limit+1]).fetchall()
        return rows

    def public_search(self,q,before,limit):
        from app.database.repositories.discovery import literal_pattern
        where="p.deleted=0 AND p.hidden=0 AND u.disabled=0 AND (LOWER(p.name) LIKE ? ESCAPE '!' OR LOWER(p.breed) LIKE ? ESCAPE '!')"
        args=[literal_pattern(q),literal_pattern(q)]
        if before:where+=' AND p.id<?';args.append(before)
        return self.db.execute('SELECT p.* FROM pets p JOIN users u ON u.id=p.user_id WHERE '+where+' ORDER BY p.id DESC LIMIT ?',[*args,limit+1]).fetchall()
