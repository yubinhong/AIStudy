"use client";

import Image from "next/image";
import { useState } from "react";

export function CaptureImage({ captureId }: { captureId: string | null }) {
  const [unavailable, setUnavailable] = useState(false);

  if (!captureId || unavailable) {
    return (
      <p className="capture-image-unavailable">
        拍题图片已过期、被删除或暂不可用。
      </p>
    );
  }

  return (
    <figure className="capture-image-figure">
      <div className="capture-image-frame">
        <Image
          alt="拍题原图"
          fill
          onError={() => setUnavailable(true)}
          sizes="(max-width: 820px) 100vw, 720px"
          src={`/api/learning/captures/${encodeURIComponent(captureId)}/image`}
          unoptimized
        />
      </div>
      <figcaption>拍题原图</figcaption>
    </figure>
  );
}
