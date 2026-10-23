// Pruebas del buscador. Uso: node web/search.test.js
const PS = require("./search.js");
let fails = 0;
function check(name, cond, extra) {
  if (!cond) fails++;
  console.log((cond ? "  ok  " : "  FALLA ") + name + (extra && !cond ? "  -> " + extra : ""));
}

const items = [
  { name: "Cerveza Heineken Lata 473cc", brand: "Heineken", size_text: "473 ml", category: "Bebidas", offers: [{ title: "Cerveza Heineken Lata 473 Cc" }, { title: "Cerveza rubia Heineken en lata 473 ml" }], stats: { n_chains: 4 } },
  { name: "Cerveza Heineken Lata 710cc", brand: "Heineken", size_text: "710 ml", category: "Bebidas", offers: [{ title: "Cerveza Heineken Lata 710 Cc" }], stats: { n_chains: 3 } },
  { name: "Cerveza Quilmes Clásica Lata 473 ml", brand: "Quilmes", size_text: "473 ml", category: "Bebidas", offers: [], stats: { n_chains: 3 } },
  { name: "Yerba Mate Taragüí con Palo 1 kg", brand: "Taragüí", size_text: "1000 g", category: "Almacén", offers: [{ title: "Yerba Mate con Palo 1 Kg Taragui" }], stats: { n_chains: 6 } },
  { name: "Gaseosa Coca-Cola Sabor Original 2,25 lt", brand: "Coca-Cola", size_text: "2250 ml", category: "Bebidas", offers: [], stats: { n_chains: 5 } },
  { name: "Leche Entera La Serenísima Sachet 1 l", brand: "La Serenísima", size_text: "1000 ml", category: "Lácteos", offers: [], stats: { n_chains: 7 } },
];
const index = PS.createIndex(items);
const top = (q, o) => { const r = PS.search(index, q, o); return { names: r.results.map(x => x.item.name), partial: r.partial }; };

console.log("Orden de palabras");
for (const q of ["473 heineken lata", "heineken lata 473", "lata 473 heineken", "Heineken 473", "HEINEKEN LATA"]) {
  const r = top(q);
  check(`"${q}" -> Heineken 473`, r.names[0] === "Cerveza Heineken Lata 473cc", r.names);
}
console.log("Unidades y equivalencias");
check('"473cc heineken" = "473 ml heineken"', top("473cc heineken").names[0] === top("473ml heineken").names[0]);
check('"710 heineken" no devuelve la de 473', top("710 heineken").names[0] === "Cerveza Heineken Lata 710cc");
check('"473 heineken" excluye 710', !top("473 heineken").names.includes("Cerveza Heineken Lata 710cc"));
check('"1 kg yerba taragui" encuentra 1000 g', top("1 kg yerba taragui").names[0] === "Yerba Mate Taragüí con Palo 1 kg");
check('"yerba 1000 g" encuentra 1 kg', top("yerba 1000 g").names[0] === "Yerba Mate Taragüí con Palo 1 kg");
check('"coca cola 2,25" encuentra 2.25 lt', top("coca cola 2,25").names[0].startsWith("Gaseosa Coca-Cola"));
check('"coca cola 2250 ml" encuentra 2.25 lt', top("coca cola 2250 ml").names[0].startsWith("Gaseosa Coca-Cola"));
console.log("Tildes, mayúsculas y plurales");
check('"serenisima leche" sin tilde', top("serenisima leche").names[0].startsWith("Leche Entera La Seren"));
check('"CERVEZAS" plural', top("CERVEZAS").names.length === 3);
console.log("Errores de tipeo");
check('"heneiken lata" (letras cambiadas)', top("heneiken lata").names[0] === "Cerveza Heineken Lata 473cc" || top("heneiken lata").names[0] === "Cerveza Heineken Lata 710cc");
check('"cervesa quilmes" (falta una z)', top("cervesa quilmes").names[0].startsWith("Cerveza Quilmes"));
check('"taragi" no coincide con cualquier cosa', !top("taragi").names.includes("Cerveza Quilmes Clásica Lata 473 ml"));
console.log("Autocompletado (prefijo en la última palabra)");
check('"heine" -> Heineken', top("heine").names[0].startsWith("Cerveza Heineken"));
check('"cerveza hei" -> Heineken', top("cerveza hei").names[0].startsWith("Cerveza Heineken"));
console.log("Sin resultados y coincidencia parcial");
check('"zzzz" no devuelve nada', top("zzzz").names.length === 0);
const parcial = top("heineken lata 999");   // 2 de 3 palabras (67 %): se muestra como parcial
check('una palabra de más: coincidencia parcial marcada', parcial.partial === true && parcial.names.length > 0, JSON.stringify(parcial));
check('menos del 67 %: no inventa resultados', top("heineken lata 999 botella").names.length === 0);
check('palabra inexistente: sin resultados y la informa', (() => { const r = PS.search(index, "473 sapucai lata"); return r.results.length === 0 && r.unknown && r.unknown[0] === "sapucai"; })());
check('marca que no está en el catálogo no se reemplaza por otras', top("473 budweiser lata").names.length === 0);
check("consulta vacía", top("   ").names.length === 0);
console.log("Normalización");
check('normalize("Taragüí  1,5 KG!")', PS.normalize("Taragüí  1,5 KG!") === "taragui 1.5 kg", PS.normalize("Taragüí  1,5 KG!"));
check('matchesText', PS.matchesText("Cerveza Heineken Lata 473cc", "473 heineken lata") === true);

console.log(fails ? `\n${fails} FALLAS` : "\nTodas las pruebas pasaron");
process.exit(fails ? 1 : 0);
