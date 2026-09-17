from marshmallow import Schema, fields, pre_load, validate

# unknown="raise" es el default de marshmallow: cualquier campo no declarado
# en el schema (ej. is_admin en un registro) hace fallar la validación con
# 400, en vez de aceptarlo silenciosamente.


def _strip_strings(data, fields_to_strip):
    if not isinstance(data, dict):
        return data
    data = dict(data)
    for key in fields_to_strip:
        if isinstance(data.get(key), str):
            data[key] = data[key].strip()
    return data


class RegisterSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=6, max=255))
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))

    @pre_load
    def strip_strings(self, data, **kwargs):
        # Sin esto, un name de puros espacios ("   ") pasaría Length(min=1)
        # y quedaría vacío recién después de hacer .strip() en el endpoint.
        return _strip_strings(data, ("email", "name"))


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=1, max=255))

    @pre_load
    def strip_strings(self, data, **kwargs):
        return _strip_strings(data, ("email",))
