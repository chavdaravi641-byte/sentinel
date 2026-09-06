"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export const GUJARAT_DISTRICTS = [
  "All Gujarat",
  "Ahmedabad",
  "Amreli",
  "Anand",
  "Aravalli",
  "Banaskantha",
  "Bharuch",
  "Bhavnagar",
  "Botad",
  "Chhota Udaipur",
  "Dahod",
  "Dang",
  "Devbhoomi Dwarka",
  "Gandhinagar",
  "Gir Somnath",
  "Jamnagar",
  "Junagadh",
  "Kheda",
  "Kutch",
  "Mahisagar",
  "Mehsana",
  "Morbi",
  "Narmada",
  "Navsari",
  "Panchmahal",
  "Patan",
  "Porbandar",
  "Rajkot",
  "Sabarkantha",
  "Surat",
  "Surendranagar",
  "Tapi",
  "Vadodara",
  "Valsad",
] as const;

type District = (typeof GUJARAT_DISTRICTS)[number];

interface DistrictContextValue {
  district: District;
  setDistrict: (district: District) => void;
}

const DistrictContext = createContext<DistrictContextValue | null>(null);

export function DistrictProvider({ children }: { children: ReactNode }) {
  const [district, setDistrictState] = useState<District>(() => {
    if (typeof window === "undefined") return "All Gujarat";
    const saved = window.localStorage.getItem("sentinel.active_district");
    return GUJARAT_DISTRICTS.includes(saved as District) ? (saved as District) : "All Gujarat";
  });

  const value = useMemo(
    () => ({
      district,
      setDistrict: (next: District) => {
        setDistrictState(next);
        window.localStorage.setItem("sentinel.active_district", next);
      },
    }),
    [district],
  );

  return <DistrictContext.Provider value={value}>{children}</DistrictContext.Provider>;
}

export function useDistrict(): DistrictContextValue {
  const context = useContext(DistrictContext);
  if (!context) throw new Error("useDistrict must be used inside DistrictProvider");
  return context;
}
