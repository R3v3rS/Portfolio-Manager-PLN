export async function getCurrentPPKPrice(): Promise<{ price: number; date: string }> {
  return Promise.resolve({
    price: 23.22,
    date: '2026-02-26',
  });
}
