from marshmallow import Schema, fields, validate

# unknown="raise" es el default de marshmallow: campos no declarados (ej. un
# "id" mandado por el cliente) hacen fallar la validación con 400.


class ProductCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(load_default="", validate=validate.Length(max=2000))
    price = fields.Decimal(required=True, places=2, validate=validate.Range(min=0))
    stock = fields.Int(load_default=0, validate=validate.Range(min=0))
    image_url = fields.Str(load_default="", validate=validate.Length(max=500))
    category_id = fields.Int(allow_none=True, load_default=None)


class ProductUpdateSchema(Schema):
    """Todos los campos opcionales y sin load_default: el resultado de
    .load() solo trae las claves que el cliente mandó, así una actualización
    parcial no pisa con valores por defecto los campos que no se tocaron."""

    name = fields.Str(validate=validate.Length(min=1, max=255))
    description = fields.Str(validate=validate.Length(max=2000))
    price = fields.Decimal(places=2, validate=validate.Range(min=0))
    stock = fields.Int(validate=validate.Range(min=0))
    image_url = fields.Str(validate=validate.Length(max=500))
    category_id = fields.Int(allow_none=True)


class StockItemSchema(Schema):
    """Un item de /internal/reserve-stock o /internal/release-stock. El
    body de esos endpoints es una lista plana (no un objeto envolvente), así
    que se valida con StockItemSchema(many=True).load(lista)."""

    product_id = fields.Int(required=True, validate=validate.Range(min=1))
    quantity = fields.Int(required=True, validate=validate.Range(min=1))
