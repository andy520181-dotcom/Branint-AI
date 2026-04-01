const MAX_EDGE = 256;
const MAX_BYTES = 2 * 1024 * 1024;

/** 读取图片文件，缩放后导出为 JPEG data URL，便于写入 localStorage */
export async function processAvatarFile(file: File): Promise<string> {
  if (!file.type.startsWith('image/')) {
    throw new Error('INVALID_TYPE');
  }
  if (file.size > MAX_BYTES) {
    throw new Error('TOO_LARGE');
  }
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      let { naturalWidth: w, naturalHeight: h } = img;
      if (!w || !h) {
        reject(new Error('INVALID_IMAGE'));
        return;
      }
      const scale = Math.min(1, MAX_EDGE / Math.max(w, h));
      const width = Math.round(w * scale);
      const height = Math.round(h * scale);
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('NO_CONTEXT'));
        return;
      }
      ctx.drawImage(img, 0, 0, width, height);
      resolve(canvas.toDataURL('image/jpeg', 0.88));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('LOAD_FAILED'));
    };
    img.src = url;
  });
}
