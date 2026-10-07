"""Local Compose backup and optional restore rehearsal into a fresh database."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[2]


def docker(*args,**kwargs):
    return subprocess.run(['docker','compose','-f',str(ROOT/'compose.yaml'),*args],cwd=ROOT,check=True,**kwargs)


def backup(rehearse=False):
    target=ROOT/'backend'/'resources'/'backups'/('snapshot-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8])
    target.mkdir(parents=True)
    dump=target/'postgres.dump'
    with dump.open('wb') as output:
        docker('exec','-T','postgres','pg_dump','-U','baichongji','-d','baichongji','-Fc',stdout=output)
    report={'created_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(dump.read_bytes()).hexdigest(),'restore_verified':False}
    for service in ('postgres','redis'):
        container=docker('ps','-q',service,capture_output=True,text=True).stdout.strip()
        report[service+'_image']=subprocess.run(['docker','inspect','--format','{{.Image}}',container],check=True,capture_output=True,text=True).stdout.strip()
    if rehearse:
        database='verify_'+uuid4().hex
        # Generated name only; never restore over the live database.
        docker('exec','-T','postgres','createdb','-U','baichongji',database)
        try:
            with dump.open('rb') as source:
                docker('exec','-T','postgres','pg_restore','-U','baichongji','--exit-on-error','-d',database,stdin=source)
            check=docker('exec','-T','postgres','psql','-U','baichongji','-d',database,'-Atc','SELECT version_num FROM alembic_version',capture_output=True,text=True)
            report['restored_revision']=check.stdout.strip();report['restore_verified']=True
        finally:docker('exec','-T','postgres','dropdb','-U','baichongji',database)
    (target/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(str(target))
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--rehearse',action='store_true')
    backup(parser.parse_args().rehearse)
