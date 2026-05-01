interface ExifData {
  iso?: number
  aperture?: string
  shutterSpeed?: string
  focalLength?: string
  cameraModel?: string
}

interface ExifDisplayProps {
  exif: ExifData
  compact?: boolean
}

export function ExifDisplay({ exif, compact = false }: ExifDisplayProps) {
  if (compact) {
    return (
      <p className="text-xs text-slate-500">
        ISO {exif.iso} · {exif.aperture} · {exif.shutterSpeed} · {exif.focalLength}
      </p>
    )
  }

  return (
    <div className="p-3 bg-slate-50 rounded-lg text-sm">
      <p className="text-slate-600">
        ISO {exif.iso} · {exif.aperture} · {exif.shutterSpeed} · {exif.focalLength}
      </p>
      {exif.cameraModel && (
        <p className="text-slate-500 text-xs mt-1">{exif.cameraModel}</p>
      )}
    </div>
  )
}
