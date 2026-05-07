/**
 * Verdecora Upload Web — Client-side upload via SAS tokens
 *
 * Flow:
 *  1. User drops/selects files in the dropzone
 *  2. For each file: POST /api/sessions/{id}/sas → get SAS URL
 *  3. PUT file to SAS URL directly (browser → Azure Blob Storage)
 *  4. On success: POST /api/sessions/{id}/files → register metadata
 *  5. Update file list via HTMX swap
 */

(function () {
  "use strict";

  const ACCEPTED_TYPES = [
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
  ];
  const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB
  const UPLOAD_STATE_PENDING = "pending";
  const UPLOAD_STATE_UPLOADING = "uploading";
  const UPLOAD_STATE_COMPLETE = "complete";
  const UPLOAD_STATE_ERROR = "error";

  /**
   * Return CSRF token from <meta> tag.
   */
  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  /**
   * Format bytes to a human-readable string.
   */
  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  /**
   * Validate a file before upload.
   */
  function validateFile(file) {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      return "Tipo de archivo no permitido. Usa PDF, JPG, PNG o TIFF.";
    }
    if (file.size > MAX_FILE_SIZE) {
      return "El archivo supera el límite de 50 MB.";
    }
    return null;
  }

  /**
   * Create a file item element for the upload list.
   */
  function createFileItemEl(file, tempId) {
    const div = document.createElement("div");
    div.className = "file-item";
    div.dataset.tempId = tempId;
    div.dataset.uploadState = UPLOAD_STATE_PENDING;
    div.draggable = false;

    const isImage = file.type.startsWith("image/");
    let iconHtml;
    if (isImage) {
      iconHtml =
        '<img class="file-thumb" src="' +
        URL.createObjectURL(file) +
        '" alt="">';
    } else {
      iconHtml = '<span class="file-icon">📄</span>';
    }

    div.innerHTML =
      iconHtml +
      '<span class="file-name">' +
      file.name +
      "</span>" +
      '<span class="file-size">' +
      formatSize(file.size) +
      "</span>" +
      '<div class="file-progress"><div class="file-progress-bar" style="width:0%"></div></div>' +
      '<button type="button" class="file-remove" title="Quitar archivo">✕</button>';

    div.querySelector(".file-remove").addEventListener("click", function () {
      div.remove();
      updateFileCount();
    });

    return div;
  }

  function bindDragStart(item) {
    if (item.dataset.dragBound === "true") {
      return;
    }
    item.addEventListener("dragstart", function (e) {
      e.dataTransfer.setData("text/plain", item.dataset.fileId);
    });
    item.dataset.dragBound = "true";
  }

  /**
   * Update the visible file count badge.
   */
  function updateFileCount() {
    const list = document.getElementById("file-list");
    const counter = document.getElementById("file-count");
    const nextBtn = document.getElementById("btn-next-preflight");
    if (!list) return;

    const items = Array.from(list.querySelectorAll(".file-item"));
    const count = items.length;
    const completedCount = items.filter(function (item) {
      return item.dataset.uploadState === UPLOAD_STATE_COMPLETE;
    }).length;
    const pendingUploads = items.filter(function (item) {
      return (
        item.dataset.uploadState === UPLOAD_STATE_PENDING ||
        item.dataset.uploadState === UPLOAD_STATE_UPLOADING
      );
    }).length;

    if (counter) {
      if (count === 0) {
        counter.textContent = "";
      } else if (pendingUploads > 0) {
        counter.textContent =
          completedCount +
          "/" +
          count +
          " archivo(s) listos · " +
          pendingUploads +
          " subiendo…";
      } else {
        counter.textContent = completedCount + " archivo(s) listos para analizar";
      }
    }
    if (nextBtn) {
      nextBtn.disabled = completedCount === 0 || pendingUploads > 0;
    }
  }

  /**
   * Request a SAS token for one file.
   */
  async function requestSas(sessionId, filename, contentType) {
    const params = new URLSearchParams({ filename: filename });
    const resp = await fetch("/api/sessions/" + sessionId + "/sas?" + params.toString(), {
      method: "POST",
      headers: {
        "X-CSRF-Token": getCsrfToken(),
      },
    });
    if (!resp.ok) {
      throw new Error("No se pudo obtener la URL de subida (SAS).");
    }
    const body = await resp.json();
    if (!(body.upload_url || body.sas_url) || !body.blob_path) {
      throw new Error("La respuesta SAS no incluye la URL o la ruta del blob.");
    }
    return {
      uploadUrl: body.upload_url || body.sas_url || "",
      blobPath: body.blob_path || "",
    };
  }

  /**
   * Upload a file directly to Azure Blob Storage via SAS URL.
   */
  async function uploadToBlob(sasUrl, file, progressBar) {
    return new Promise(function (resolve, reject) {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", sasUrl, true);
      xhr.setRequestHeader("x-ms-blob-type", "BlockBlob");
      xhr.setRequestHeader("Content-Type", file.type);

      xhr.upload.addEventListener("progress", function (e) {
        if (e.lengthComputable && progressBar) {
          const pct = Math.round((e.loaded / e.total) * 100);
          progressBar.style.width = pct + "%";
        }
      });

      xhr.addEventListener("load", function () {
        if (xhr.status >= 200 && xhr.status < 300) {
          if (progressBar) {
            progressBar.style.width = "100%";
            progressBar.classList.add("complete");
          }
          resolve();
        } else {
          reject(new Error("Error al subir a almacenamiento: " + xhr.status));
        }
      });

      xhr.addEventListener("error", function () {
        reject(new Error("Error de red al subir el archivo."));
      });

      xhr.send(file);
    });
  }

  /**
   * Register uploaded file metadata with the backend.
   */
  async function registerFile(sessionId, filename, blobPath, contentType, size) {
    const resp = await fetch("/api/sessions/" + sessionId + "/files", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": getCsrfToken(),
      },
      body: JSON.stringify({
        filename: filename,
        blob_path: blobPath,
        mime_type: contentType,
        size_bytes: size,
      }),
    });
    if (!resp.ok) {
      throw new Error("No se pudo registrar el archivo.");
    }
    return resp.json();
  }

  /**
   * Process a single file: SAS → Blob upload → register.
   */
  async function processFile(sessionId, file, fileItemEl) {
    const progressBar = fileItemEl.querySelector(".file-progress-bar");
    fileItemEl.dataset.uploadState = UPLOAD_STATE_UPLOADING;
    updateFileCount();
    try {
      const sas = await requestSas(sessionId, file.name, file.type);
      await uploadToBlob(sas.uploadUrl, file, progressBar);
      const registration = await registerFile(
        sessionId,
        file.name,
        sas.blobPath,
        file.type,
        file.size
      );
      fileItemEl.dataset.uploadState = UPLOAD_STATE_COMPLETE;
      fileItemEl.dataset.fileId = registration.file_id || fileItemEl.dataset.tempId;
      fileItemEl.draggable = true;
      bindDragStart(fileItemEl);
      updateFileCount();
    } catch (err) {
      if (progressBar) {
        progressBar.classList.add("error");
      }
      fileItemEl.dataset.uploadState = UPLOAD_STATE_ERROR;
      updateFileCount();
      console.error("Upload failed for " + file.name + ":", err);
      throw err;
    }
  }

  /**
   * Handle file selection (from input or drop).
   */
  function handleFiles(files, sessionId) {
    const list = document.getElementById("file-list");
    if (!list) return;

    const emptyState = list.querySelector(".empty-state");
    if (emptyState) {
      emptyState.remove();
    }

    Array.from(files).forEach(function (file, idx) {
      const error = validateFile(file);
      if (error) {
        alert(file.name + ": " + error);
        return;
      }

      const tempId = "temp-" + Date.now() + "-" + idx;
      const el = createFileItemEl(file, tempId);
      list.appendChild(el);

      if (sessionId) {
        processFile(sessionId, file, el).catch(function () {
          // error already logged; keep UI item to show error state
        });
      }
    });

    updateFileCount();
  }

  /**
   * Initialize dropzone interactions.
   */
  function initDropzone() {
    const dropzone = document.getElementById("dropzone");
    if (!dropzone) return;

    const fileInput = dropzone.querySelector('input[type="file"]');
    const sessionId = dropzone.dataset.sessionId || "";

    if (!sessionId) {
      console.error("Upload session is missing; the upload page must create a session before file selection.");
      return;
    }

    dropzone.addEventListener("dragover", function (e) {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", function () {
      dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", function (e) {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      if (e.dataTransfer && e.dataTransfer.files.length > 0) {
        handleFiles(e.dataTransfer.files, sessionId);
      }
    });

    if (fileInput) {
      fileInput.addEventListener("change", function () {
        handleFiles(fileInput.files, sessionId);
        fileInput.value = "";
      });
    }

    // "Add more files" button
    var addBtn = document.getElementById("btn-add-files");
    if (addBtn && fileInput) {
      addBtn.addEventListener("click", function () {
        fileInput.click();
      });
    }
  }

  /**
   * Initialize page grouping drag-and-drop.
   */
  function initGrouping() {
    document.querySelectorAll(".albaran-group").forEach(function (group) {
      group.addEventListener("dragover", function (e) {
        e.preventDefault();
        group.classList.add("drag-over");
      });

      group.addEventListener("dragleave", function () {
        group.classList.remove("drag-over");
      });

      group.addEventListener("drop", function (e) {
        e.preventDefault();
        group.classList.remove("drag-over");
        var fileId = e.dataTransfer.getData("text/plain");
        var item = document.querySelector('[data-file-id="' + fileId + '"]');
        if (item) {
          group.querySelector(".albaran-group-files").appendChild(item);
        }
      });
    });

    document.querySelectorAll(".file-item[draggable='true']").forEach(function (item) {
      bindDragStart(item);
    });
  }

  // Boot
  document.addEventListener("DOMContentLoaded", function () {
    initDropzone();
    initGrouping();
  });

  // Re-init after HTMX swaps
  document.addEventListener("htmx:afterSwap", function () {
    initGrouping();
    updateFileCount();
  });
})();
