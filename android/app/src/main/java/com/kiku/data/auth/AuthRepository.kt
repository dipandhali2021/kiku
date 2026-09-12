package com.kiku.data.auth

import com.google.firebase.auth.FirebaseAuth
import com.kiku.BuildConfig
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.tasks.await

/**
 * Firebase Auth wrapper.
 *
 * Onboarding rule: nobody sees a sign-up wall. The first launch signs in
 * anonymously so the user can import a clip within seconds; a real account can
 * be linked later with [linkGoogleAccount], which preserves the same uid and
 * therefore all saved words.
 */
@Singleton
class AuthRepository @Inject constructor(
    private val auth: FirebaseAuth,
) {

    val uid: String? get() = auth.currentUser?.uid

    val isAnonymous: Boolean get() = auth.currentUser?.isAnonymous ?: true

    /** Signs in anonymously if there is no session yet. Safe to call repeatedly. */
    suspend fun ensureSignedIn(): String {
        auth.currentUser?.let { return it.uid }
        return auth.signInAnonymously().await().user!!.uid
    }

    /**
     * Bearer token for API calls, or a dev token on debug builds so the app
     * works against a local backend without a Firebase project.
     */
    suspend fun idToken(): String? {
        val user = auth.currentUser ?: runCatching { ensureSignedIn() }.let { auth.currentUser }
        if (user == null) {
            return if (BuildConfig.DEV_AUTH) "dev:local-user" else null
        }
        return runCatching { user.getIdToken(false).await().token }.getOrNull()
            ?: if (BuildConfig.DEV_AUTH) "dev:${user.uid}" else null
    }

    /**
     * Upgrades the anonymous account in place, keeping the uid.
     *
     * @param idToken Google ID token obtained via Credential Manager.
     */
    suspend fun linkGoogleAccount(idToken: String) {
        val credential = com.google.firebase.auth.GoogleAuthProvider.getCredential(idToken, null)
        val current = auth.currentUser
        if (current != null && current.isAnonymous) {
            // Linking keeps the uid, so saved words survive the upgrade.
            runCatching { current.linkWithCredential(credential).await() }
                .onFailure {
                    // Credential already belongs to an existing account: sign
                    // into it instead. The anonymous progress is abandoned,
                    // which is the expected behaviour for a returning user.
                    auth.signInWithCredential(credential).await()
                }
        } else {
            auth.signInWithCredential(credential).await()
        }
    }

    suspend fun signOut() {
        auth.signOut()
        ensureSignedIn() // never leave the app in a token-less state
    }
}
