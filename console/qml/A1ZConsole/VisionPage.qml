pragma ComponentBehavior: Bound

import QtQuick

Item {
    id: root
    objectName: "visionPage"

    required property var theme
    required property var controller

    CameraPanel {
        anchors.fill: parent
        theme: root.theme
        controller: root.controller
    }
}
