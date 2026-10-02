/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional raster tile template for the Geo basemap. */
  readonly VITE_MAP_TILE_URL?: string
  /** Optional CARTO basemap key (unkeyed CARTO tiles carry a watermark). */
  readonly VITE_CARTO_API_KEY?: string
  /** Attribution HTML shown with a custom tile source. */
  readonly VITE_MAP_TILE_ATTRIBUTION?: string
}
interface ImportMeta {
  readonly env: ImportMetaEnv
}
