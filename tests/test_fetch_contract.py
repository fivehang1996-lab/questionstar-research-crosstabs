import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NODE=os.environ.get('WJX_NODE_PATH') or shutil.which('node')


@unittest.skipUnless(NODE,'Node runtime required for offline fetch tests')
class FetchTests(unittest.TestCase):
    def fetch(self,directory,mode='normal'):
        env=dict(os.environ,WJX_NODE_PATH=NODE,WJX_CLI_PATH=str(ROOT/'tests/mock_wjx_cli.mjs'),WJX_ID_SALT='offline-fixture-salt',
                 WJX_API_KEY='offline-fixture-key',WJX_LINKAGE_FIELD='source_detail',WJX_TEST_MODE=mode)
        return subprocess.run([NODE,str(ROOT/'scripts/fetch_wjx_dataset.mjs'),'123',str(directory)],env=env,text=True,capture_output=True)

    def test_stable_anonymous_ids_and_text_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            one,two=Path(tmp)/'one',Path(tmp)/'two'
            self.assertEqual(self.fetch(one).returncode,0)
            self.assertEqual(self.fetch(two).returncode,0)
            a=json.loads((one/'responses.deidentified.json').read_text())
            b=json.loads((two/'responses.deidentified.json').read_text())
            self.assertEqual([r['respondent_id'] for r in a],[r['respondent_id'] for r in b])
            self.assertNotIn('TEXT_MUST_NOT_LEAK',(one/'responses.deidentified.json').read_text())
            self.assertTrue(a[0]['answer_items']['a']['answered'])
            self.assertIn('linkage_key',a[0])
            receipt=json.loads((one/'fetch-receipt.json').read_text())
            self.assertEqual(receipt['expected_records'],receipt['api_valid_records'])

    def test_duplicate_pages_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=self.fetch(Path(tmp)/'source','duplicate')
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Duplicate response',result.stderr)

    def test_existing_snapshot_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'source'
            self.assertEqual(self.fetch(target).returncode,0)
            self.assertNotEqual(self.fetch(target).returncode,0)


if __name__=='__main__':unittest.main()
