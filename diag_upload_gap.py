import sqlite3, sys
from collections import Counter
from pathlib import Path
BASE = Path('..').resolve()
sys.path.insert(0, 'src')
from application.report_parser import ReportParser
DB = BASE / 'data' / 'imc_dashboard.db'
UPLOADS = BASE / 'data' / 'uploads'
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
meta_count = conn.execute('SELECT COUNT(*) FROM report_metadata').fetchone()[0]
pdfs = sorted(UPLOADS.glob('*.pdf')) if UPLOADS.exists() else []
print('report_metadata', meta_count)
print('uploads_pdf', len(pdfs))
print('gap', len(pdfs)-meta_count)
db_paths = {Path(row[0]).resolve() for row in conn.execute('SELECT file_path FROM report_metadata WHERE file_path IS NOT NULL') if row[0]}
orphan = [p for p in pdfs if p.resolve() not in db_paths]
print('orphan_pdfs', len(orphan))
parser = ReportParser()
parse_failures = []
date_to_files = {}
for pdf in pdfs:
    try:
        report = parser.parse(str(pdf))
        date_to_files.setdefault(report.report_date.isoformat(), []).append(pdf.name)
    except Exception as exc:
        parse_failures.append((pdf.name, str(exc)))
print('unique_dates_from_uploads', len(date_to_files))
print('parse_failures', len(parse_failures))
multi = {d:fs for d,fs in date_to_files.items() if len(fs)>1}
print('dates_with_multiple_pdfs', len(multi))
err = Counter()
for _,msg in parse_failures:
    err[msg.split('\n')[0][:120]] += 1
print('--- failure reasons ---')
for k,v in err.most_common(20):
    print(v, k)
print('--- failed files ---')
for name,msg in parse_failures:
    print(name, ':', msg[:100])
