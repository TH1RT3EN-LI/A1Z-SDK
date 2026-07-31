pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

Item {
    id: root
    objectName: "teachingPage"

    required property var theme
    required property var controller
    property bool motionDraftPending: false

    PageScrollView {
        id: teachingScroll

        anchors.fill: parent

        ColumnLayout {
            width: teachingScroll.availableWidth
            spacing: root.theme.spacingM

            TeachingPlaybackPanel {
                Layout.fillWidth: true
                theme: root.theme
                controller: root.controller
                motionDraftPending: root.motionDraftPending
            }
        }
    }
}
