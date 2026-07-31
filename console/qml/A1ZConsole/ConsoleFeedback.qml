import QtQuick

InlineBanner {
    id: root

    required property var controller

    text: root.controller.operationFeedbackState !== "idle"
          ? root.controller.operationFeedbackMessage
          : root.controller.lastError.length > 0
            ? root.controller.lastError
            : root.controller.statusText
    level: root.controller.operationFeedbackState === "error"
           || root.controller.operationFeedbackState === "uncertain"
             ? "error"
           : root.controller.operationFeedbackState === "warning"
             ? "warn"
           : root.controller.operationFeedbackState === "success"
             ? "success"
           : root.controller.operationFeedbackState === "idle"
             && root.controller.lastError.length > 0
             ? "error" : "info"
    dismissible: root.controller.operationFeedbackState !== "idle"
                 && root.controller.operationFeedbackDismissible
    onDismissed: root.controller.dismissOperationFeedback()
}
