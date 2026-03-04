// CLM-lite minimal JS — most interactivity handled by HTMX + Bootstrap
document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss alerts after 5s
    document.querySelectorAll('.alert-dismissible').forEach(function(alert) {
        setTimeout(function() { alert.remove(); }, 5000);
    });
});
