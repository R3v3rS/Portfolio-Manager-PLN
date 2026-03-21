class ValidationError(Exception):
    def __init__(self, errors, message='Validation failed'):
        super().__init__(message)
        self.message = message
        self.errors = errors


class BusinessRuleError(Exception):
    def __init__(self, message, code='business_rule_error', status_code=400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
