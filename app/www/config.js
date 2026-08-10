/* Auralis Natura app — runtime config.
   Low-cost by design: the shop uses Stripe Payment Links (no backend fees, no
   PaymentIntent server, no keys in the app). Offers are fetched live from the
   API when online (so prices/links change without an app update); these values
   are the offline fallback. */
window.AN_CONFIG = {
  // The portal backend (Flask on the Mac / EU server, via Cloudflare tunnel).
  // Override for local testing with ?api=http://127.0.0.1:5056
  API_BASE: "https://api.auralisnatura.com",

  // Offline fallback for the Programme shop. Live values come from GET /api/app/offers.
  // buy_url = a Stripe Payment Link (create in the Stripe Dashboard → Payment Links).
  OFFERS: [
    { key: "root",     name: "Klarheit",                 price: 199,
      tagline: "Tiefen-Erstanalyse + persönlicher Bericht",
      buy_url: "https://buy.stripe.com/fZucN4ay0d60eGog4z1ZS00" },
    { key: "bloom",    name: "Wandel",                   price: 399,
      tagline: "4 Wochen begleitetes Programm",
      buy_url: "https://buy.stripe.com/8x2aEW9tW3vqgOwbOj1ZS01" },
    { key: "flourish", name: "Balance",                  price: 899,
      tagline: "12 Wochen intensive Begleitung",
      buy_url: "" }   // ← paste the Balance Stripe Payment Link here (falls back to a free intro call until set)
  ],

  BOOK_URL: "https://api.auralisnatura.com/book",
  CONTACT_EMAIL: "team@auralisnatura.com",
  PRIVACY_URL: "https://www.auralisnatura.com/impressum.html"
};
