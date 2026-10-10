"""Local SQLite snapshots, bounded automatic retention and guarded restoration."""
import hashlib
import sqlite3
import threading
from pathlib import Path
from datetime import datetime,date
from uuid import uuid4
from contextlib import closing
import time
from api.exceptions import ValidationError

_lock=threading.RLock()
_release_signature=None


def recognized(name):
    return name.endswith('.db') and name.startswith(('manual-','daily-','update-','before-'))


def directory(database):
    path=Path(database).resolve().parent/'backups'
    path.mkdir(parents=True,exist_ok=True)
    return path


def validate(path):
    try:
        with closing(sqlite3.connect(f'{path.as_uri()}?mode=ro',uri=True)) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError()
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'portfolios','transactions','holdings'}.issubset(tables):raise ValueError()
            for table,required in {'portfolios':{'id','name','account_type'},'transactions':{'id','portfolio_id','ticker','date','type','quantity','price','total_value'},'holdings':{'id','portfolio_id','ticker','quantity','total_cost','average_buy_price'}}.items():
                if not required.issubset({r[1] for r in db.execute('PRAGMA table_info('+table+')')}):raise ValueError()
            if db.execute('PRAGMA foreign_key_check').fetchone():raise ValueError()
    except (sqlite3.Error,ValueError): raise ValidationError('Plik nie jest poprawną kopią bazy aplikacji.') from None


def create(database,kind='manual'):
    source=Path(database).resolve()
    if not source.exists() or not source.stat().st_size:return None
    if kind not in ('manual','daily','update','before-restore'):raise ValidationError('Nieprawidłowy rodzaj kopii.')
    with _lock:
        folder=directory(database)
        name=f'{kind}-{datetime.now().strftime("%Y%m%d-%H%M%S")}-{uuid4().hex[:8]}.db'
        target=folder/name;temp=folder/(name+'.tmp')
        try:
            with closing(sqlite3.connect(source)) as src,closing(sqlite3.connect(temp)) as dst:src.backup(dst)
            validate(temp)
            temp.replace(target)
        finally:
            if temp.exists():temp.unlink()
        # Only managed automatic copies are rotated. Manual and rescue copies stay.
        for prefix,keep in (('daily-',14),('update-',10)):
            copies=sorted(folder.glob(prefix+'*.db'),key=lambda p:p.stat().st_mtime,reverse=True)
            for old in copies[keep:]:old.unlink()
        return name


def automatic(database,before_update=False):
    global _release_signature
    source=Path(database).resolve()
    if not source.exists() or not source.stat().st_size:return
    with _lock:
        folder=directory(database)
        if before_update:
            if _release_signature is None:
                root=Path(__file__).resolve().parent
                sources=sorted(root.glob('*.py'))+sorted((root/'modules').rglob('*.py'))+sorted((root/'services').rglob('*.py'))
                sources+=sorted((root.parent/'frontend'/'src').rglob('*.tsx'))+sorted((root.parent/'frontend'/'src').rglob('*.ts'))+sorted((root.parent/'frontend'/'src').rglob('*.css'))
                _release_signature=hashlib.sha256(b''.join(str(p.relative_to(root.parent)).encode()+p.read_bytes() for p in sources)).hexdigest()
            signature=_release_signature
            marker=folder/'.schema-signature'
            if not marker.exists() or marker.read_text()!=signature:
                create(database,'update');marker.write_text(signature)
        if not list(folder.glob('daily-'+date.today().strftime('%Y%m%d')+'-*.db')):create(database,'daily')


def workspace(database):
    folder=directory(database);items=[]
    for p in folder.glob('*.db'):
        if p.is_symlink() or not recognized(p.name):continue
        stat=p.stat();items.append({'name':p.name,'created_at':datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds'),'size':stat.st_size,
                                   'kind':p.name.split('-')[0] if p.name.split('-')[0] in ('manual','daily','update','before') else 'other'})
    items.sort(key=lambda p:p['created_at'],reverse=True)
    return {'items':items,'automatic_daily':True,'daily_retention':14,'update_retention':10}


def restore(database,name,create_rescue=True):
    with _lock:
        folder=directory(database)
        if not isinstance(name,str) or Path(name).name!=name or '/' in name or '\\' in name or not recognized(name):
            raise ValidationError('Wybierz kopię z listy.')
        source=(folder/name).resolve()
        if source.parent!=folder.resolve() or not source.is_file() or (folder/name).is_symlink():raise ValidationError('Kopia nie istnieje.')
        validate(source)
        rescue=create(database,'before-restore') if create_rescue else None
        try:
            deadline=time.monotonic()+15
            def progress(*args):
                if time.monotonic()>deadline:raise TimeoutError()
            with closing(sqlite3.connect(f'{source.as_uri()}?mode=ro',uri=True)) as src,closing(sqlite3.connect(database,timeout=15)) as dest:
                src.backup(dest,pages=200,sleep=.05,progress=progress)
        except (sqlite3.Error,TimeoutError) as e:raise ValidationError('Nie udało się przywrócić bazy. Kopia bieżących danych została zachowana.') from e
        return {'restored':name,'rescue_copy':rescue}
