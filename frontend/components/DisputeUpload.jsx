"use client";

import { useState } from "react";
import { Paperclip, UploadCloud, Video } from "lucide-react";

export default function DisputeUpload({ files: controlledFiles, onFilesChange, title = "Dispute evidence" }) {
  const [internalFiles, setInternalFiles] = useState([]);
  const files = controlledFiles ?? internalFiles;

  function handleChange(event) {
    const nextFiles = Array.from(event.target.files || []);
    if (!controlledFiles) {
      setInternalFiles(nextFiles);
    }
    onFilesChange?.(nextFiles);
  }

  return (
    <div className="card rounded-[24px] p-5">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-rose-50 p-3 text-rose-700">
          <UploadCloud className="h-5 w-5" />
        </div>
        <div>
          <h3 className="font-bold">{title}</h3>
          <p className="text-sm text-stone-600">Upload clear photos, screenshots, or short videos to support your claim.</p>
        </div>
      </div>

      <label className="mt-5 flex cursor-pointer flex-col items-center justify-center rounded-[22px] border border-dashed border-stone-300 bg-stone-50 px-4 py-8 text-center">
        <Paperclip className="h-6 w-6 text-stone-500" />
        <span className="mt-3 font-semibold">Tap to upload images or videos</span>
        <span className="mt-1 text-sm text-stone-500">Optimized for mobile evidence collection</span>
        <input
          type="file"
          accept="image/*,video/*"
          multiple
          onChange={handleChange}
          className="hidden"
        />
      </label>

      <div className="mt-4 space-y-2">
        {files.length === 0 ? (
          <p className="text-sm text-stone-500">No files selected yet.</p>
        ) : (
          files.map((file) => (
            <div key={`${file.name}-${file.size}`} className="flex items-center justify-between rounded-2xl bg-stone-50 px-4 py-3 text-sm">
              <div>
                <p className="font-semibold text-stone-700">{file.name}</p>
                <p className="text-stone-500">{Math.round(file.size / 1024)} KB</p>
              </div>
              <Video className="h-4 w-4 text-stone-500" />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
