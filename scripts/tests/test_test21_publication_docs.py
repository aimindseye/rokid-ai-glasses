import tempfile
import unittest
from pathlib import Path
from shutil import copytree

from scripts.research.cxr.verify_test21_publication_docs import verify


class PublicationDocsContract(unittest.TestCase):
    def test_verify_passes_on_overlay_copy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src_docs = Path('docs')
            src_scripts = Path('scripts')
            copytree(src_docs, root / 'docs')
            copytree(src_scripts, root / 'scripts')
            rc = verify(root)
            self.assertEqual(rc, 0)

    def test_diagram_doc_has_multiple_mermaid_blocks(self):
        text = Path('docs/research/cxr/test21-static-binder-boundary-diagrams.md').read_text(encoding='utf-8')
        self.assertGreaterEqual(text.count('```mermaid'), 5)

    def test_callback_reference_has_all_21_rows(self):
        text = Path('docs/research/cxr/test21-callback-transaction-reference.md').read_text(encoding='utf-8')
        rows = [
            line for line in text.splitlines()
            if line.startswith('| ') and '`com.rokid.sprite.aiapp.externalapp.' in line and not line.startswith('| Interface label ')
        ]
        self.assertEqual(len(rows), 21)


if __name__ == '__main__':
    unittest.main()
