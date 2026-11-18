document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-toast]").forEach((toast) => {
        const closeButton = toast.querySelector("[data-toast-close]");

        if (!closeButton) {
            return;
        }

        closeButton.addEventListener("click", () => {
            toast.remove();
        });
    });
});