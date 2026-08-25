FROM php:8.3-apache-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libfreetype6-dev \
        libicu-dev \
        libjpeg62-turbo-dev \
        libpng-dev \
        libzip-dev \
        passwd \
        unzip \
    && docker-php-ext-configure gd \
        --with-freetype \
        --with-jpeg \
    && docker-php-ext-install -j"$(nproc)" \
        gd \
        intl \
        mysqli \
        opcache \
        pdo \
        pdo_mysql \
        zip \
    && pecl install redis \
    && docker-php-ext-enable redis \
    && a2enmod rewrite headers \
    && sed -ri \
        's/AllowOverride None/AllowOverride All/g' \
        /etc/apache2/apache2.conf \
    && echo "ServerName localhost" \
        > /etc/apache2/conf-available/servername.conf \
    && a2enconf servername \
    && rm -rf /var/lib/apt/lists/*

RUN printf '\n# Permisos predeterminados de la aplicación\numask 0027\n' \
    >> /etc/apache2/envvars

COPY redis-session.ini \
    /usr/local/etc/php/conf.d/zz-redis-session.ini

COPY docker-entrypoint.sh \
    /usr/local/bin/wordpress-entrypoint

RUN chmod 0755 /usr/local/bin/wordpress-entrypoint

ENTRYPOINT ["wordpress-entrypoint"]
CMD ["apache2-foreground"]
