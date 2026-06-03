(function () {
    "use strict";

    function initDropZone(input) {
        var zone = document.createElement("div");
        zone.className = "video-drop-zone";

        var hint = document.createElement("span");
        hint.className = "video-drop-hint";
        hint.textContent = "⬇ Glisser une vidéo ici ou cliquer pour parcourir";
        zone.appendChild(hint);

        // Progress bar (hidden by default)
        var progressWrap = document.createElement("div");
        progressWrap.className = "video-progress-wrap";
        var progressTrack = document.createElement("div");
        progressTrack.className = "video-progress-bar-track";
        var progressBar = document.createElement("div");
        progressBar.className = "video-progress-bar";
        progressTrack.appendChild(progressBar);
        progressWrap.appendChild(progressTrack);
        var progressLabel = document.createElement("span");
        progressLabel.className = "video-progress-label";
        progressWrap.appendChild(progressLabel);
        zone.appendChild(progressWrap);

        input.parentNode.insertBefore(zone, input.nextSibling);

        function setFilename(name) {
            hint.textContent = "✓ " + name;
            zone.classList.add("has-file");
        }

        function showProgress(pct) {
            progressWrap.style.display = "block";
            progressBar.style.width = pct + "%";
            progressLabel.textContent = Math.round(pct) + " %";
        }

        function hideProgress() {
            progressWrap.style.display = "none";
        }

        // Drag events
        zone.addEventListener("dragenter", function (e) { e.preventDefault(); zone.classList.add("drag-over"); });
        zone.addEventListener("dragover",  function (e) { e.preventDefault(); zone.classList.add("drag-over"); });
        zone.addEventListener("dragleave", function ()  { zone.classList.remove("drag-over"); });
        zone.addEventListener("dragend",   function ()  { zone.classList.remove("drag-over"); });

        zone.addEventListener("drop", function (e) {
            e.preventDefault();
            zone.classList.remove("drag-over");
            var files = e.dataTransfer.files;
            if (!files.length) return;
            var file = files[0];
            try {
                var dt = new DataTransfer();
                dt.items.add(file);
                input.files = dt.files;
                input.dispatchEvent(new Event("change", { bubbles: true }));
            } catch (_) {}
            setFilename(file.name);
        });

        // Click on zone → open file picker
        zone.addEventListener("click", function () { input.click(); });

        // Sync when user picks via dialog
        input.addEventListener("change", function () {
            if (input.files && input.files.length > 0) {
                setFilename(input.files[0].name);
            }
        });

        // Pre-fill if a file is already set (edit form)
        if (input.value) {
            var parts = input.value.split(/[\\/]/);
            setFilename(parts[parts.length - 1]);
        }

        return { showProgress: showProgress, hideProgress: hideProgress, input: input };
    }

    function interceptFormSubmit(form, dropZones) {
        form.addEventListener("submit", function (e) {
            // Only intercept if at least one file input has a file selected
            var hasFile = dropZones.some(function (dz) {
                return dz.input.files && dz.input.files.length > 0;
            });
            if (!hasFile) return; // normal submit, no big file

            e.preventDefault();

            var data = new FormData(form);
            var xhr  = new XMLHttpRequest();

            // Show progress on the first drop zone that has a file
            var active = dropZones.find(function (dz) {
                return dz.input.files && dz.input.files.length > 0;
            });

            if (active) active.showProgress(0);

            xhr.upload.addEventListener("progress", function (ev) {
                if (ev.lengthComputable && active) {
                    active.showProgress((ev.loaded / ev.total) * 100);
                }
            });

            xhr.addEventListener("load", function () {
                if (active) active.hideProgress();
                // Django admin redirects after save — follow the final URL
                var finalUrl = xhr.responseURL || form.action;
                // The response itself is the resulting admin page; navigate to it
                window.location.href = finalUrl;
            });

            xhr.addEventListener("error", function () {
                if (active) {
                    active.hideProgress();
                    active.showProgress(0); // reset bar
                }
                alert("Erreur lors de l'envoi du fichier.");
            });

            xhr.open(form.method || "POST", form.action || window.location.href, true);
            xhr.send(data);
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        var inputs = Array.from(document.querySelectorAll('input[type="file"]'));
        var dropZones = inputs.map(initDropZone);

        // Hook into the closest form that contains these inputs
        var form = inputs.length && inputs[0].closest("form");
        if (form && dropZones.length) {
            interceptFormSubmit(form, dropZones);
        }
    });
}());
