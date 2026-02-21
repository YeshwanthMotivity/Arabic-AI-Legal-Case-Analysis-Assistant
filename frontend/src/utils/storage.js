/**
 * Safe localStorage wrapper with error handling
 */

const STORAGE_KEY_PREFIX = 'arabicLegal_';

/**
 * Safely get item from localStorage
 * @param {string} key - Storage key
 * @param {any} defaultValue - Value if key not found or error
 * @returns {any} Stored value or default
 */
export const getStorageItem = (key, defaultValue = null) => {
    try {
        const item = localStorage.getItem(STORAGE_KEY_PREFIX + key);

        if (item === null) {
            return defaultValue;
        }

        return JSON.parse(item);
    } catch (error) {
        if (error instanceof SyntaxError) {
            console.warn(`Invalid JSON stored for key "${key}":`, error);
        } else if (error instanceof Error && error.name === 'QuotaExceededError') {
            console.error(`localStorage quota exceeded for key "${key}"`, error);
        } else {
            console.warn(`Could not access localStorage for key "${key}":`, error);
        }

        return defaultValue;
    }
};

/**
 * Safely set item in localStorage
 * @param {string} key - Storage key
 * @param {any} value - Value to store
 * @returns {boolean} True if successful, false otherwise
 */
export const setStorageItem = (key, value) => {
    try {
        localStorage.setItem(STORAGE_KEY_PREFIX + key, JSON.stringify(value));
        return true;
    } catch (error) {
        if (error instanceof Error && error.name === 'QuotaExceededError') {
            console.error(`localStorage quota exceeded. Cannot store "${key}". Try clearing old conversations.`);

            // Optional: Auto-cleanup oldest conversations
            try {
                cleanupOldConversations();
                localStorage.setItem(STORAGE_KEY_PREFIX + key, JSON.stringify(value));
                return true;
            } catch {
                return false;
            }
        } else {
            console.error(`Could not save to localStorage for key "${key}":`, error);
            return false;
        }
    }
};

/**
 * Safely remove item from localStorage
 * @param {string} key - Storage key
 * @returns {boolean} True if successful
 */
export const removeStorageItem = (key) => {
    try {
        localStorage.removeItem(STORAGE_KEY_PREFIX + key);
        return true;
    } catch (error) {
        console.error(`Could not remove from localStorage for key "${key}":`, error);
        return false;
    }
};

/**
 * Check if localStorage is available
 * @returns {boolean} True if localStorage is accessible
 */
export const isStorageAvailable = () => {
    try {
        const test = '__storage_test__';
        localStorage.setItem(test, test);
        localStorage.removeItem(test);
        return true;
    } catch {
        return false;
    }
};

/**
 * Clean up old conversations to free space
 */
export const cleanupOldConversations = (keepCount = 10) => {
    try {
        const conversations = getStorageItem('conversations', []);

        if (conversations.length > keepCount) {
            // Sort by date and keep only newest
            const sorted = conversations
                .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
                .slice(0, keepCount);

            setStorageItem('conversations', sorted);
            console.log(`Cleaned up old conversations. Kept ${keepCount} newest.`);
        }
    } catch (error) {
        console.error('Error cleaning up conversations:', error);
    }
};
