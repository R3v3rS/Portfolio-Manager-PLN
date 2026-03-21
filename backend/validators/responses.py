from flask import jsonify


def error_response(message, status_code=400, code='request_error', details=None):
    payload = {
        'error': {
            'code': code,
            'message': message,
        }
    }
    if details:
        payload['error']['details'] = details
    return jsonify(payload), status_code


def validation_error_response(message, errors, status_code=400):
    return error_response(message, status_code=status_code, code='validation_error', details=errors)
