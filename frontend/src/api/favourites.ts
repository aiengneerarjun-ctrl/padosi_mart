import { api } from "./client";
import { Geo, ProductCard, StoreCard } from "./shop";

export const favStores = (geo: Geo) =>
  api<StoreCard[]>("/users/me/favourites/stores", { query: { ...geo, limit: 50 } });

export const favProducts = (geo: Geo) =>
  api<ProductCard[]>("/users/me/favourites/products", { query: { ...geo, limit: 50 } });

export const setFavStore = (id: string, on: boolean) =>
  api<void>(`/users/me/favourites/stores/${id}`, { method: on ? "PUT" : "DELETE" });

export const setFavProduct = (id: string, on: boolean) =>
  api<void>(`/users/me/favourites/products/${id}`, { method: on ? "PUT" : "DELETE" });