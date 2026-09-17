from marshmallow import Schema, fields, pre_load, validate

# unknown="raise" es el default de marshmallow: rechaza campos no declarados.


class OrderItemInputSchema(Schema):
    product_id = fields.Int(required=True, validate=validate.Range(min=1))
    quantity = fields.Int(required=True, validate=validate.Range(min=1))


class CreateOrderSchema(Schema):
    items = fields.List(
        fields.Nested(OrderItemInputSchema), required=True, validate=validate.Length(min=1)
    )
    shipping_address = fields.Str(required=True, validate=validate.Length(min=1, max=500))

    @pre_load
    def strip_address(self, data, **kwargs):
        # Sin esto, una dirección de puros espacios pasaría Length(min=1).
        if isinstance(data, dict) and isinstance(data.get("shipping_address"), str):
            data = dict(data)
            data["shipping_address"] = data["shipping_address"].strip()
        return data
