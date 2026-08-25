<?php
/**
 * Plugin Name: Indicador del backend
 * Description: Muestra qué réplica web atendió la solicitud.
 */

function laboratorio_backend_name(): string {
    $backend = getenv('BACKEND_NAME');

    if ($backend !== false && $backend !== '') {
        return $backend;
    }

    return gethostname() ?: 'desconocido';
}

add_action(
    'admin_bar_menu',
    static function (WP_Admin_Bar $admin_bar): void {
        $admin_bar->add_node(
            [
                'id'    => 'laboratorio-backend',
                'title' => 'Backend: ' . esc_html(laboratorio_backend_name()),
                'href'  => false,
            ]
        );
    },
    100
);

add_action(
    'send_headers',
    static function (): void {
        header('X-WordPress-Backend: ' . laboratorio_backend_name());
    }
);
