// Clear all browser cache and localStorage
// Run this in browser console or add to page

(function() {
    console.log('🧹 Clearing all cache and storage...');
    
    // Clear localStorage
    try {
        localStorage.clear();
        console.log('✅ localStorage cleared');
    } catch (e) {
        console.error('❌ Error clearing localStorage:', e);
    }
    
    // Clear sessionStorage
    try {
        sessionStorage.clear();
        console.log('✅ sessionStorage cleared');
    } catch (e) {
        console.error('❌ Error clearing sessionStorage:', e);
    }
    
    // Clear IndexedDB (if used)
    if ('indexedDB' in window) {
        indexedDB.databases().then(databases => {
            databases.forEach(db => {
                indexedDB.deleteDatabase(db.name);
            });
            console.log('✅ IndexedDB cleared');
        }).catch(e => {
            console.error('❌ Error clearing IndexedDB:', e);
        });
    }
    
    // Clear service worker cache (if registered)
    if ('serviceWorker' in navigator && 'caches' in window) {
        caches.keys().then(names => {
            names.forEach(name => {
                caches.delete(name);
            });
            console.log('✅ Service worker caches cleared');
        }).catch(e => {
            console.error('❌ Error clearing service worker caches:', e);
        });
    }
    
    // Force reload
    console.log('🔄 Reloading page...');
    setTimeout(() => {
        window.location.reload(true);
    }, 500);
})();

