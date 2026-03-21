from flask import jsonify


def success_response(payload=None, message='OK', status_code=200):
    body = {
        'status': 'success',
        'message': message,
        'payload': payload,
    }
    return jsonify(body), status_code


def error_response(message, status_code=400, code='request_error', details=None):
    body = {
        'status': 'error',
        'error': {
            'code': code,
            'message': message,
        }
    }
    if details is not None:
        body['error']['details'] = details
    return jsonify(body), status_code


def validation_error_response(message, errors, status_code=400):
    return error_response(
        message,
        status_code=status_code,
        code='validation_error',
        details=errors,
    )
