export interface Category {
  id: number;
  name: string;
}

export interface Product {
  id: number;
  name: string;
  description: string;
  price: number;
  stock: number;
  image_url: string;
  category: Category | null;
  created_at: string;
}

export interface User {
  id: number;
  email: string;
  name: string;
  is_admin: boolean;
  created_at: string;
}

export interface OrderItem {
  product_id: number;
  product_name: string;
  unit_price: number;
  quantity: number;
  subtotal: number;
}

export interface Order {
  id: number;
  user_id: number;
  status: string;
  total: number;
  shipping_address: string;
  created_at: string;
  items: OrderItem[];
}

export interface CartItem {
  product: Product;
  quantity: number;
}
