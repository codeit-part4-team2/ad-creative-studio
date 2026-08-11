import { apiFetch } from "./client";
import type { Product } from "@/lib/types/api";

export async function createProduct(input: {
  image: File;
  productName: string;
  price: number;
  sellingPoints?: string;
}): Promise<Product> {
  const form = new FormData();
  form.append("image", input.image);
  form.append("product_name", input.productName);
  form.append("price", String(input.price));
  if (input.sellingPoints) form.append("selling_points", input.sellingPoints);

  return apiFetch<Product>("/api/v1/products", {
    method: "POST",
    body: form,
  });
}
