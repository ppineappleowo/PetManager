import tempfile
import unittest
from unittest.mock import patch
from app.database.repositories.knowledge import KnowledgeRepository


class KnowledgeVersionTests(unittest.TestCase):
    def test_failed_build_preserves_old_index_and_reopen_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=KnowledgeRepository(directory,'knowledge_test')
            repo.add(ids=['old'],documents=['旧知识'],embeddings=[[1.,0.,0.]],metadatas=[{'source':'old'}])
            old=repo.collection.name
            with patch.object(repo,'publish',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):repo.rebuild(['新资料'],[[0.,1.,0.]],[{'source':'new'}])
            self.assertEqual(repo.collection.name,old)
            self.assertEqual(repo.get()['ids'],['old'])
            new=repo.rebuild(['新资料'],[[0.,1.,0.]],[{'source':'new'}])
            reopened=KnowledgeRepository(directory,'knowledge_test')
            self.assertEqual(reopened.collection.name,new)
            reopened.rollback(old)
            self.assertEqual(reopened.get()['ids'],['old'])
            with self.assertRaises(ValueError):reopened.rollback('unknown')
            reopened.close();repo.close()
