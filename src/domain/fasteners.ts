export type FastenerType = {
  id: string;
  name: string;
  image: string;
};

export const FASTENER_TYPES: FastenerType[] = [
  { id: "nut", name: "Nut (น็อต)", image: "/Nut.png" },
  { id: "washer", name: "Washer (แหวนรอง)", image: "/Washer.png" },
];
