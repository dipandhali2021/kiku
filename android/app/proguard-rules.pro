# kotlinx.serialization keeps generated serializers via @Serializable; R8 needs
# help finding them because they are referenced reflectively.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**

-if @kotlinx.serialization.Serializable class **
-keepclassmembers class <1> {
    static <1>$Companion Companion;
    static **$* *;
}
-keepclassmembers class **$* implements kotlinx.serialization.KSerializer {
    static <1> INSTANCE;
}

# Retrofit interfaces are reflective.
-keep,allowobfuscation,allowshrinking interface com.kiku.data.remote.KikuApi
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation
-keep,allowobfuscation,allowshrinking class retrofit2.Response

# OkHttp platform warnings on the JVM-only code paths.
-dontwarn okhttp3.internal.platform.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
