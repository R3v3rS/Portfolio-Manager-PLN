from flask import Blueprint,current_app,request
from urllib.parse import urlparse
from api.exceptions import ValidationError
from api.response import success_response
import backup_service as service

backups_bp=Blueprint('backups',__name__,url_prefix='/api/backups')


def local_write():
    origin=request.headers.get('Origin')
    if origin:
        parsed=urlparse(origin)
        if parsed.scheme not in ('http','https') or parsed.hostname not in ('127.0.0.1','localhost') or parsed.port not in (5000,5173):
            raise ValidationError('Kopiami zarządza się z lokalnej aplikacji.')


@backups_bp.get('/')
def list_backups():
    return success_response(service.workspace(current_app.config['DATABASE']))


@backups_bp.post('/')
def make_backup():
    local_write()
    name=service.create(current_app.config['DATABASE'])
    return success_response({'name':name},status=201)


@backups_bp.post('/restore')
def restore_backup():
    local_write()
    data=request.get_json(silent=True) or {}
    if data.get('confirmation')!='PRZYWRÓĆ':raise ValidationError('Potwierdź przywrócenie wpisując PRZYWRÓĆ.')
    result=service.restore(current_app.config['DATABASE'],data.get('name'))
    from database import close_db,init_db
    close_db()
    try:init_db(current_app._get_current_object())
    except Exception:
        close_db()
        service.restore(current_app.config['DATABASE'],result['rescue_copy'],create_rescue=False)
        close_db();init_db(current_app._get_current_object())
        raise ValidationError('Ta kopia nie jest zgodna z obecną wersją aplikacji. Przywrócono poprzedni stan.') from None
    from portfolio_service import PortfolioService
    from price_service import PriceService
    PortfolioService.clear_cache()
    for name in ('_price_cache','_price_cache_updated_at','_metadata_cache','_metadata_cache_updated_at'):
        cache=getattr(PriceService,name,None)
        if isinstance(cache,dict):cache.clear()
    PriceService._quotes_cache={'lite':{},'full':{}}
    PriceService._quotes_cache_updated_at={'lite':{},'full':{}}
    return success_response(result)
